import os
import re
import json
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# --- ORTAM DEĞİŞKENLERİ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SPOR_EKRANI_FB_URL = "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda"

KNOWN_CHANNELS = [
    "TRT 1", "TRT Spor", "TRT Spor Yıldız", "TRT Tabii", "Tabii",
    "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN Sports 4", "beIN Sports Haber", "beIN SPORTS",
    "S Sport Plus", "S Sport 1", "S Sport 2", "S Sport",
    "Exxen", "TV8,5", "TV8.5", "TV8",
    "A Spor", "ATV", "A Para",
    "Tivibu Spor 1", "Tivibu Spor 2", "Tivibu Spor 3", "Tivibu Spor 4", "Tivibu Spor",
    "Smart Spor", "Smart Spor 2", "Spor Smart", "D-Smart GO"
]


def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[-] Hata: TELEGRAM_TOKEN veya CHAT_ID ortam değişkenleri tanımlı değil.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("[+] Telegram bildirimi başarıyla gönderildi.")
        return True
    except Exception as e:
        print(f"[-] Telegram mesajı gönderilemedi: {e}")
        return False


def get_match_channels(detail_url: str) -> str:
    if not detail_url:
        return "Bilinmiyor"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(detail_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "Bilinmiyor"

        soup = BeautifulSoup(res.text, "html.parser")
        page_text = soup.get_text(separator=" ")

        found = []
        for ch in KNOWN_CHANNELS:
            pattern = rf"\b{re.escape(ch)}\b"
            if re.search(pattern, page_text, re.IGNORECASE):
                if not any(ch.lower() in item.lower() for item in found):
                    found.append(ch)

        return ", ".join(found) if found else "Bilinmiyor"
    except Exception as e:
        print(f"[-] Kanal hatası: {e}")
        return "Bilinmiyor"


def fetch_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(SPOR_EKRANI_FB_URL, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[-] Sayfa yüklenemedi: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    matches = []

    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]

            for item in items:
                if item.get("@type") == "SportsEvent" or "homeTeam" in item:
                    home = item.get("homeTeam", {}).get("name", "")
                    away = item.get("awayTeam", {}).get("name", "")
                    start_date = item.get("startDate", "")
                    competition = item.get("description") or item.get("name", "Futbol Karşılaşması")
                    detail_url = item.get("url", "")

                    if "fenerbahçe" in home.lower() or "fenerbahce" in home.lower() or \
                       "fenerbahçe" in away.lower() or "fenerbahce" in away.lower():
                        matches.append({
                            "home": home,
                            "away": away,
                            "competition": competition,
                            "start_date": start_date,
                            "detail_url": detail_url
                        })
        except Exception:
            continue

    return matches


def check_and_notify():
    print("[*] Test modu: İlk maç çekiliyor...")

    matches = fetch_matches()
    if not matches:
        print("[-] Herhangi bir maç verisi bulunamadı.")
        return

    match = matches[0]
    print(f"[+] Maç bulundu: {match['home']} vs {match['away']}")

    detail_url = match.get("detail_url")
    channel = get_match_channels(detail_url)

    msg = (
        "🧪 <b>TEST BİLDİRİMİ</b>\n\n"
        f"⚽ <b>{match['home']} - {match['away']}</b>\n"
        f"🏆 <i>{match['competition']}</i>\n"
        f"📺 <b>Kanal:</b> {channel}\n"
        f"📅 <b>Tarih:</b> {match.get('start_date', 'Bilinmiyor')}\n"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
