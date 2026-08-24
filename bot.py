import os
import re
import json
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SPOR_EKRANI_URL = "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda"

# Sadece maç yayınında geçebilecek ana spor kanalları
VALID_CHANNELS = [
    "TRT 1", "TRT Spor Yıldız", "TRT Spor", "TRT Tabii", "Tabii",
    "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN Sports 4", "beIN Sports Haber", "beIN Sports MAX 1", "beIN Sports MAX 2",
    "S Sport Plus", "S Sport 1", "S Sport 2", "S Sport",
    "Exxen", "TV8,5", "TV8.5", "TV8",
    "A Spor", "ATV",
    "Tivibu Spor 1", "Tivibu Spor 2", "Tivibu Spor 3", "Tivibu Spor 4", "Tivibu Spor",
    "Smart Spor 1", "Smart Spor 2", "Smart Spor", "D-Smart GO"
]


def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[-] Hata: TELEGRAM_TOKEN veya CHAT_ID tanımlı değil.")
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
        print("[+] Telegram mesajı iletildi.")
        return True
    except Exception as e:
        print(f"[-] Telegram hatası: {e}")
        return False


def get_channel_from_detail_page(detail_url: str) -> str:
    """Maçın kendi özel sayfasına gidip sadece yayıncı alanını tarar."""
    if not detail_url:
        return "Bilinmiyor"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(detail_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "Bilinmiyor"
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Sadece yayın/kanal alanını hedefle (tv, channel, broadcast veya card sınıfları)
        broadcast_block = soup.find("div", class_=re.compile(r"broadcast|channel|tv|yayin|detail", re.I))
        target_soup = broadcast_block if broadcast_block else soup
        
        # Metin ve kanal logolarının alt/title değerlerini topla
        text = target_soup.get_text(separator=" ")
        for img in target_soup.find_all("img"):
            text += f" {img.get('alt', '')} {img.get('title', '')} {img.get('src', '')}"

        found = []
        for ch in VALID_CHANNELS:
            pattern = rf"(?:\b|[^a-zA-Z0-9]){re.escape(ch)}(?:\b|[^a-zA-Z0-9])"
            if re.search(pattern, text, re.IGNORECASE):
                # Çakışmaları önle (örn: beIN Sports 1 varsa beIN Sports ekleme)
                if not any(ch.lower() in item.lower() for item in found):
                    found.append(ch)

        return " / ".join(found) if found else "Bilinmiyor"
    except Exception:
        return "Bilinmiyor"


def fetch_matches():
    """Spor Ekranı Fenerbahçe sayfasından maç verilerini toplar."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(SPOR_EKRANI_URL, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
    except Exception as e:
        print(f"[-] Sayfa açılamadı: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    matches = []

    # 1. JSON-LD üzerinden maçları tara
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "SportsEvent" or "homeTeam" in item:
                    home = item.get("homeTeam", {}).get("name", "Fenerbahçe")
                    away = item.get("awayTeam", {}).get("name", "Rakip")
                    start_date = item.get("startDate", "")
                    comp = item.get("description") or item.get("name", "Futbol Karşılaşması")
                    url = item.get("url", "")
                    
                    matches.append({
                        "home": home,
                        "away": away,
                        "competition": comp,
                        "start_date": start_date,
                        "detail_url": url
                    })
        except Exception:
            continue

    # 2. JSON-LD yoksa HTML kartlarını tara
    if not matches:
        for a in soup.find_all("a", href=re.compile(r"maci-hangi-kanalda|fenerbahce", re.I)):
            title = a.get_text(separator=" ").strip()
            if "fenerbahçe" in title.lower() or "fenerbahce" in title.lower():
                href = a["href"] if a["href"].startswith("http") else f"https://www.sporekrani.com{a['href']}"
                matches.append({
                    "home": "Fenerbahçe",
                    "away": "Rakip Takım",
                    "competition": "Süper Lig / Avrupa",
                    "start_date": "",
                    "detail_url": href
                })
                break

    return matches


def check_and_notify():
    print("[*] Fenerbahçe maçı taranıyor...")
    matches = fetch_matches()

    if not matches:
        print("[-] Maç bulunamadı.")
        return

    # Sıradaki ilk maçı al
    match = matches[0]
    
    # Maç saati ayıklama
    start_date_raw = match.get("start_date", "")
    match_time = "20:00"
    if "T" in start_date_raw:
        try:
            tz_tr = timezone(timedelta(hours=3))
            dt = datetime.fromisoformat(start_date_raw.replace("Z", "+00:00")).astimezone(tz_tr)
            match_time = dt.strftime("%H:%M")
        except Exception:
            match_time = start_date_raw.split("T")[-1][:5]

    # Kanal bilgisini detay sayfasından çek
    channel = get_channel_from_detail_page(match.get("detail_url"))

    # Şablon Mesaj
    msg = (
        "📅 <b>BUGÜN FENERBAHÇEMİZİN MAÇI VAR!</b>\n\n"
        f"⚽ <b>{match['home']} - {match['away']}</b>\n"
        f"🏆 <i>{match['competition']}</i>\n"
        f"📺 <b>Kanal:</b> {channel}\n"
        f"⏰ <b>Saat:</b> {match_time}"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
