import os
import re
import requests
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


def get_match_channels_from_text(text: str) -> str:
    """Metin içindeki bilinen TV kanallarını bulur."""
    found = []
    for ch in KNOWN_CHANNELS:
        pattern = rf"\b{re.escape(ch)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            if not any(ch.lower() in item.lower() for item in found):
                found.append(ch)
    return ", ".join(found) if found else "Bilinmiyor"


def fetch_matches():
    """Spor Ekranı HTML yapısını doğrudan tarar."""
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

    # Sayfadaki tüm bağlantıları ve maç bloklarını tara
    cards = soup.find_all(["div", "tr", "li", "article"])
    for card in cards:
        text = card.get_text(separator=" ").strip()
        if "fenerbahçe" in text.lower() or "fenerbahce" in text.lower():
            # Maç satırında tarih ve rakip aranıyor
            link = card.find("a", href=True)
            href = link["href"] if link else ""
            if href and not href.startswith("http"):
                href = f"https://www.sporekrani.com{href}"

            channel = get_match_channels_from_text(text)
            
            # Kart içinden anlamlı başlık çıkarımı
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if len(lines) >= 2:
                matches.append({
                    "raw_text": " | ".join(lines[:4]),
                    "channel": channel,
                    "url": href
                })

    return matches


def check_and_notify():
    print("[*] Test modu: HTML üzerinden maçlar taranıyor...")

    matches = fetch_matches()
    if not matches:
        # Alternatif: Sayfanın saf metninde kanal tara
        print("[-] Blok bulunamadı, genel sayfa metni kontrol ediliyor...")
        res = requests.get(SPOR_EKRANI_FB_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        ch = get_match_channels_from_text(res.text)
        
        msg = (
            "🧪 <b>TEST BİLDİRİMİ (Genel Tarama)</b>\n\n"
            "⚽ <b>Fenerbahçe Karşılaşması</b>\n"
            f"📺 <b>Bulunan Kanallar:</b> {ch}\n"
            "🔗 Spor Ekranı sayfası başarıyla okundu."
        )
        send_telegram_message(msg)
        return

    # İlk bulunan veriyi gönder
    first = matches[0]
    msg = (
        "🧪 <b>TEST BİLDİRİMİ</b>\n\n"
        f"📋 <b>Maç Bilgisi:</b> {first['raw_text']}\n"
        f"📺 <b>Kanal:</b> {first['channel']}\n"
    )

    send_telegram_message(msg)


if __name__ == "__main__":
    check_and_notify()
