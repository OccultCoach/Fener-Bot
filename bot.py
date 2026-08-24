import os
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

KNOWN_CHANNELS = [
    "TRT 1", "TRT Spor Yıldız", "TRT Spor", "TRT Tabii", "Tabii",
    "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN Sports 4", "beIN Sports Haber",
    "S Sport Plus", "S Sport 1", "S Sport 2", "S Sport",
    "Exxen", "TV8,5", "TV8.5", "TV8",
    "A Spor", "ATV",
    "Tivibu Spor 1", "Tivibu Spor 2", "Tivibu Spor 3", "Tivibu Spor 4", "Tivibu Spor",
    "Smart Spor 1", "Smart Spor 2", "Smart Spor", "D-Smart GO"
]


def send_telegram_message(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[-] Hata: Secret değerleri eksik.")
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
        print("[+] Telegram bildirimi gönderildi.")
        return True
    except Exception as e:
        print(f"[-] Telegram hatası: {e}")
        return False


def get_channel_for_match(home: str, away: str) -> str:
    """Maça özel yayıncı kanalını web üzerinden arar."""
    query = f"{home} {away} hangi kanalda sporekrani"
    search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            # Yalnızca ilk 2 arama sonucunun metnini tara (diğer maçlar karışmasın)
            snippets = soup.find_all("a", class_="result__snippet")[:2]
            text = " ".join([s.get_text() for s in snippets])

            found = []
            for ch in KNOWN_CHANNELS:
                pattern = rf"(?:\b|[^a-zA-Z0-9]){re.escape(ch)}(?:\b|[^a-zA-Z0-9])"
                if re.search(pattern, text, re.IGNORECASE):
                    if not any(ch.lower() in item.lower() for item in found):
                        found.append(ch)

            if found:
                return " / ".join(found)
    except Exception as e:
        print(f"[-] Kanal arama hatası: {e}")

    # Varsayılan turnuva tahmini (Kanal bulunamazsa genel resmi yayıncılar)
    return "TRT 1 / beIN Sports"


def get_fenerbahce_next_match():
    """Fenerbahçe'nin sıradaki resmi maçını çeker."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # Açık fikstür API'si üzerinden Fenerbahçe (Team ID / Arama)
    try:
        # Alternatif hızlı fikstür kaynağı
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/tur.1/scoreboard"
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            events = data.get("events", [])
            for event in events:
                name = event.get("name", "")
                if "Fenerbahce" in name or "Fenerbahçe" in name:
                    comps = event.get("competitions", [{}])[0]
                    competitors = comps.get("competitors", [])
                    home = competitors[0].get("team", {}).get("displayName", "")
                    away = competitors[1].get("team", {}).get("displayName", "")
                    date_raw = comps.get("date", "")
                    league = event.get("season", {}).get("name", "Süper Lig")
                    
                    return {
                        "home": home,
                        "away": away,
                        "competition": league,
                        "date_raw": date_raw
                    }
    except Exception:
        pass

    # Yedek veri (Spor Ekranı Genel Başlık Taraması)
    try:
        sp_url = "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda"
        res = requests.get(sp_url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        
        for item in soup.find_all(["h2", "h3", "a"]):
            text = item.get_text(separator=" ").strip()
            if " - " in text and ("fenerbahçe" in text.lower() or "fenerbahce" in text.lower()):
                parts = text.split(" - ")
                return {
                    "home": parts[0].strip(),
                    "away": parts[1].split()[0].strip() if len(parts) > 1 else "Rakip Takım",
                    "competition": "Süper Lig / Avrupa",
                    "date_raw": ""
                }
    except Exception:
        pass

    # Varsayılan Maç Bilgisi
    return {
        "home": "Fenerbahçe",
        "away": "Rakip Takım",
        "competition": "Trendyol Süper Lig",
        "date_raw": ""
    }


def check_and_notify():
    print("[*] Maç bilgileri toplanıyor...")
    match = get_fenerbahce_next_match()

    home = match["home"]
    away = match["away"]
    competition = match["competition"]
    date_raw = match["date_raw"]

    # Saat formatlama
    match_time = "20:00"
    if date_raw:
        try:
            tz_tr = timezone(timedelta(hours=3))
            dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00")).astimezone(tz_tr)
            match_time = dt.strftime("%H:%M")
        except Exception:
            pass

    # Kanalı sadece bu maç için ara
    channel = get_channel_for_match(home, away)

    # İstenen Şablon
    msg = (
        "📅 <b>BUGÜN FENERBAHÇEMİZİN MAÇI VAR!</b>\n\n"
        f"⚽ <b>{home} - {away}</b>\n"
        f"🏆 <i>{competition}</i>\n"
        f"📺 <b>Kanal:</b> {channel}\n"
        f"⏰ <b>Saat:</b> {match_time}"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
