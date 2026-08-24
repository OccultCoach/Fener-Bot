import os
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

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
        print("[-] Hata: Secret'lar eksik.")
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
        print("[+] Telegram bildirimi iletildi.")
        return True
    except Exception as e:
        print(f"[-] Telegram hatası: {e}")
        return False


def find_channel_from_web() -> tuple:
    """Fenerbahçe'nin sıradaki maçını ve kanal bilgisini arar."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # 1. Kaynak: Spor Ekranı Arama / Liste
    urls = [
        "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda",
        "https://www.sporekrani.com/"
    ]

    all_text = ""
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                # img alt ve title etiketlerini de topla
                img_tags = " ".join([f"{img.get('alt', '')} {img.get('title', '')} {img.get('src', '')}" for img in soup.find_all("img")])
                all_text += " " + soup.get_text(separator=" ") + " " + img_tags
        except Exception:
            continue

    # 2. Alternatif Arama Motoru Snippet Taraması (DuckDuckGo HTML)
    try:
        ddg_url = "https://html.duckduckgo.com/html/?q=site:sporekrani.com+fenerbahce+hangi+kanalda"
        r = requests.get(ddg_url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            snippets = " ".join([a.get_text() for a in soup.find_all("a", class_="result__snippet")])
            titles = " ".join([a.get_text() for a in soup.find_all("a", class_="result__title")])
            all_text += f" {snippets} {titles}"
    except Exception:
        pass

    # Kanalları ayıkla
    found_channels = []
    for ch in KNOWN_CHANNELS:
        pattern = rf"(?:\b|[^a-zA-Z0-9]){re.escape(ch)}(?:\b|[^a-zA-Z0-9])"
        if re.search(pattern, all_text, re.IGNORECASE):
            if not any(ch.lower() in c.lower() for c in found_channels):
                found_channels.append(ch)

    # Maç başlığı çıkarma (Örn: Lyon - Fenerbahçe veya rakip bilgisi)
    match_title = "Fenerbahçe Karşılaşması"
    match_re = re.search(r"([A-Za-zÇĞİÖŞÜçğıöşü\s]+[-–]\s*Fenerbahçe|Fenerbahçe\s*[-–]\s*[A-Za-zÇĞİÖŞÜçğıöşü\s]+)", all_text)
    if match_re:
        cleaned = match_re.group(1).strip()
        if len(cleaned) < 50 and "\n" not in cleaned:
            match_title = cleaned

    channel_str = ", ".join(found_channels) if found_channels else "Şifresiz / Yayıncı Belirtilmemiş"
    return match_title, channel_str


def check_and_notify():
    print("[*] Fenerbahçe maçı ve kanal bilgisi taranıyor...")
    
    match_title, channels = find_channel_from_web()
    
    print(f"[+] Bulunan Maç: {match_title}")
    print(f"[+] Bulunan Kanal(lar): {channels}")

    msg = (
        "📅 <b>FENERBAHÇE MAÇ BİLGİSİ</b>\n\n"
        f"⚽ <b>{match_title}</b>\n"
        f"📺 <b>Yayın Kanalı:</b> {channels}\n\n"
        "<i>(Bilgiler Spor Ekranı ve yayın akışlarından derlenmiştir.)</i>"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
