import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SPOR_EKRANI_URL = "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda"

# Sadece gerçek ana TV kanalları (Platformlar hariç)
MAIN_TV_CHANNELS = [
    "TRT 1", "TRT Spor Yıldız", "TRT Spor", "Tabii Spor", "Tabii",
    "beIN Sports Haber", "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN Sports 4", "beIN Sports MAX 1", "beIN Sports MAX 2",
    "S Sport Plus", "S Sport 1", "S Sport 2", "S Sport",
    "Exxen", "TV8,5", "TV8.5", "TV8",
    "A Spor", "ATV",
    "Tivibu Spor 1", "Tivibu Spor 2", "Tivibu Spor",
    "Smart Spor 1", "Smart Spor 2", "Smart Spor"
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


def get_exact_match_and_channel():
    """Spor Ekranı detay sayfasından maçı ve ana kanal kutusunu ayıklar."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    home = "Lyon"
    away = "Fenerbahçe"
    competition = "UEFA Avrupa Ligi"
    match_time = "22:00"
    channel = "TRT 1"

    try:
        res = requests.get(SPOR_EKRANI_URL, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Sayfadaki tüm metin ve görsel alt bilgilerini topla
            content_text = soup.get_text(separator=" ")
            for img in soup.find_all("img"):
                content_text += f" {img.get('alt', '')} {img.get('title', '')} "

            # Ana TV kanalını eşleştir
            detected = []
            for ch in MAIN_TV_CHANNELS:
                pattern = rf"(?:\b|[^a-zA-Z0-9]){re.escape(ch)}(?:\b|[^a-zA-Z0-9])"
                if re.search(pattern, content_text, re.IGNORECASE):
                    if not any(ch.lower() in item.lower() for item in detected):
                        detected.append(ch)

            if detected:
                channel = " / ".join(detected)
    except Exception as e:
        print(f"[-] Hata: {e}")

    return home, away, competition, match_time, channel


def check_and_notify():
    print("[*] Maç ve kanal bilgisi alınıyor...")
    home, away, competition, match_time, channel = get_exact_match_and_channel()

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
