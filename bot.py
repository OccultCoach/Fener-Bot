import os
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# --- ORTAM DEĞİŞKENLERİ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SPOR_EKRANI_URL = "https://www.sporekrani.com/fenerbahce-maclari-hangi-kanalda"

# Tanımlı Türk ve Popüler Spor Kanalları
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
        print("[+] Telegram bildirimi başarıyla gönderildi.")
        return True
    except Exception as e:
        print(f"[-] Telegram hatası: {e}")
        return False


def extract_channels_from_element(soup_element) -> str:
    """HTML bloğundaki metinleri ve kanal logosu img etiketlerini tarar."""
    found = []

    # 1. Metin içeriği
    text_content = soup_element.get_text(separator=" ")

    # 2. img etiketlerindeki alt, title ve src alanları (Logo tarama)
    images = soup_element.find_all("img")
    for img in images:
        alt = img.get("alt", "")
        title = img.get("title", "")
        src = img.get("src", "")
        text_content += f" {alt} {title} {src} "

    # Kanalları ara
    for ch in KNOWN_CHANNELS:
        # Regex ile büyük/küçük harf duyarsız arama
        pattern = rf"(?:^|[^a-zA-Z0-9]){re.escape(ch)}(?:$|[^a-zA-Z0-9])"
        if re.search(pattern, text_content, re.IGNORECASE):
            clean_ch = ch.replace("Sports", "Sports").strip()
            if not any(clean_ch.lower() in item.lower() for item in found):
                found.append(clean_ch)

    return ", ".join(found) if found else "Bilinmiyor"


def fetch_fb_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(SPOR_EKRANI_URL, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"[-] Sayfa yüklenemedi: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    matches = []

    # Sayfadaki tüm olası maç kartlarını / satırlarını bul
    rows = soup.find_all(["div", "li", "tr"])

    for row in rows:
        row_text = row.get_text(separator=" ").strip()
        
        # Fenerbahçe maçı içeren satırları süz
        if ("fenerbahçe" in row_text.lower() or "fenerbahce" in row_text.lower()) and len(row_text) < 400:
            # Tarih ve saat formatı (örn: 20:00, 21:45 veya 15.01 / 2026 gibi)
            time_match = re.search(r"\b(\d{1,2}:\d{2})\b", row_text)
            date_match = re.search(r"\b(\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?)\b", row_text)
            
            # Kanal çıkarımı
            channels = extract_channels_from_element(row)
            
            # Anlamlı satır başlığı
            lines = [l.strip() for l in row_text.splitlines() if l.strip()]
            title = " - ".join(lines[:2]) if lines else row_text[:80]

            matches.append({
                "title": title,
                "time": time_match.group(1) if time_match else "Belirtilmemiş",
                "date": date_match.group(1) if date_match else "Belirtilmemiş",
                "channel": channels,
                "raw_soup": row
            })

    # Tekrarlayan verileri temizle
    unique_matches = []
    seen = set()
    for m in matches:
        if m["title"] not in seen and len(m["title"]) > 10:
            seen.add(m["title"])
            unique_matches.append(m)

    return unique_matches


def check_and_notify():
    print("[*] Fenerbahçe maçları taranıyor...")

    matches = fetch_fb_matches()
    
    if not matches:
        # Alternatif: Tüm sayfayı genel olarak tara
        print("[-] Özel satır bulunamadı, tam sayfa kanalı taranıyor...")
        res = requests.get(SPOR_EKRANI_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        channel = extract_channels_from_element(soup)

        msg = (
            "🧪 <b>TEST BİLDİRİMİ (Fenerbahçe)</b>\n\n"
            "⚽ <b>Fenerbahçe Karşılaşması</b>\n"
            f"📺 <b>Kanal:</b> {channel}\n"
        )
        send_telegram_message(msg)
        return

    # İlk sıradaki maçı gönder (Test)
    first = matches[0]
    print(f"[+] İlk maç bulundu: {first['title']} - Kanal: {first['channel']}")

    msg = (
        "🧪 <b>TEST BİLDİRİMİ</b>\n\n"
        f"⚽ <b>{first['title']}</b>\n"
        f"📺 <b>Kanal:</b> {first['channel']}\n"
        f"⏰ <b>Saat:</b> {first['time']}\n"
        f"📅 <b>Tarih:</b> {first['date']}\n"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
