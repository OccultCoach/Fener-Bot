import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date

# ============================================================
# AYARLAR
# ============================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

TEAM_URL = "https://www.sporekrani.com/home/team/fenerbahce/"

# Sadece gerçek TV kanalları.
# Platform / frekans / uydu bilgileri alınmaz.
MAIN_TV_CHANNELS = [
    "TRT 1",
    "TRT Spor Yıldız",
    "TRT Spor",
    "tabii Spor",
    "Tabii Spor",
    "Tabii",
    "beIN Sports Haber",
    "Bein Sports Haber",
    "beIN Sports 1",
    "Bein Sports 1",
    "beIN Sports 2",
    "Bein Sports 2",
    "beIN Sports 3",
    "Bein Sports 3",
    "beIN Sports 4",
    "Bein Sports 4",
    "beIN Sports MAX 1",
    "Bein Sports MAX 1",
    "beIN Sports MAX 2",
    "Bein Sports MAX 2",
    "S Sport Plus",
    "S Sport 1",
    "S Sport 2",
    "S Sport",
    "Exxen",
    "TV8,5",
    "TV8.5",
    "TV8",
    "A Spor",
    "ATV",
    "Tivibu Spor 1",
    "Tivibu Spor 2",
    "Tivibu Spor",
    "Smart Spor 1",
    "Smart Spor 2",
    "Smart Spor",
    "Spor Smart",
    "TV 100",
    "TV100",
    "FB TV",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIMEOUT = 15

# Aynı maç için tekrar tekrar bildirim göndermemek amacıyla
STATE_FILE = "bot_state.json"


# ============================================================
# HTTP
# ============================================================

def get_page(url: str):
    """Sayfayı indirir."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        return response.text

    except requests.RequestException as e:
        print(f"[-] Sayfa alınamadı: {e}")
        return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(message: str) -> bool:

    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[-] Hata: TELEGRAM_TOKEN veya CHAT_ID eksik.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10
        )

        response.raise_for_status()

        print("[+] Telegram bildirimi gönderildi.")
        return True

    except requests.RequestException as e:
        print(f"[-] Telegram hatası: {e}")
        return False


# ============================================================
# DURUM DOSYASI
# ============================================================

def load_state():
    """Daha önce bildirilmiş maçları yükler."""

    if not os.path.exists(STATE_FILE):
        return {
            "notified_matches": []
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "notified_matches": []
        }


def save_state(state):

    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2
            )

    except Exception as e:
        print(f"[-] State dosyası kaydedilemedi: {e}")


# ============================================================
# KANAL TESPİTİ
# ============================================================

def detect_channels(text: str):

    detected = []

    normalized_text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    for channel in MAIN_TV_CHANNELS:

        pattern = (
            rf"(?<![a-zA-Z0-9])"
            rf"{re.escape(channel)}"
            rf"(?![a-zA-Z0-9])"
        )

        if re.search(
            pattern,
            normalized_text,
            re.IGNORECASE
        ):

            # Aynı kanalın farklı yazımlarını tekrar ekleme
            already_exists = any(
                c.lower() == channel.lower()
                for c in detected
            )

            if not already_exists:
                detected.append(channel)

    # Daha temiz görünmesi için bazı varyasyonları normalize et
    normalized_channels = []

    for channel in detected:

        lower = channel.lower()

        if lower in ["bein sports 1"]:
            display_name = "beIN Sports 1"

        elif lower in ["bein sports 2"]:
            display_name = "beIN Sports 2"

        elif lower in ["bein sports 3"]:
            display_name = "beIN Sports 3"

        elif lower in ["bein sports 4"]:
            display_name = "beIN Sports 4"

        elif lower in ["bein sports haber"]:
            display_name = "beIN Sports Haber"

        elif lower == "bein sports max 1":
            display_name = "beIN Sports MAX 1"

        elif lower == "bein sports max 2":
            display_name = "beIN Sports MAX 2"

        elif lower in ["tabii spor"]:
            display_name = "tabii Spor"

        elif lower == "tv100":
            display_name = "TV 100"

        elif lower == "spor smart":
            display_name = "Spor Smart"

        else:
            display_name = channel

        if display_name not in normalized_channels:
            normalized_channels.append(display_name)

    return normalized_channels


# ============================================================
# MAÇ DETAY SAYFASI
# ============================================================

def parse_match_detail(url: str):

    print(f"[*] Maç detay sayfası okunuyor: {url}")

    html = get_page(url)

    if not html:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Sayfadaki tüm metni al
    text = soup.get_text(
        separator=" ",
        strip=True
    )

    # --------------------------------------------------------
    # TARİH
    # --------------------------------------------------------

    date_match = re.search(
        r"(\d{2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})",
        text
    )

    match_date = None

    if date_match:

        day = int(date_match.group(1))
        year = int(date_match.group(3))

        months = {
            "Ocak": 1,
            "Şubat": 2,
            "Mart": 3,
            "Nisan": 4,
            "Mayıs": 5,
            "Haziran": 6,
            "Temmuz": 7,
            "Ağustos": 8,
            "Eylül": 9,
            "Ekim": 10,
            "Kasım": 11,
            "Aralık": 12,
        }

        month_name = date_match.group(2)

        month = months.get(month_name)

        if month:
            match_date = date(
                year,
                month,
                day
            )

    # --------------------------------------------------------
    # SAAT
    # --------------------------------------------------------

    time_match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        text
    )

    match_time = None

    if time_match:
        match_time = (
            f"{int(time_match.group(1)):02d}:"
            f"{time_match.group(2)}"
        )

    # --------------------------------------------------------
    # MAÇ / TAKIMLAR
    # --------------------------------------------------------

    home_team = None
    away_team = None

    # Sayfadaki başlık üzerinden daha güvenli yöntem
    title = soup.find("h1")

    if title:

        title_text = title.get_text(
            " ",
            strip=True
        )

        match_teams = re.search(
            r"(.+?)\s+vs\s+(.+?)\s+maçı",
            title_text,
            re.IGNORECASE
        )

        if match_teams:

            home_team = match_teams.group(1).strip()
            away_team = match_teams.group(2).strip()

    # --------------------------------------------------------
    # ORGANİZASYON
    # --------------------------------------------------------

    competition = None

    # Sayfadaki bilinen organizasyonlardan ilkini bul
    competitions = [
        "UEFA Şampiyonlar Ligi Play-Off",
        "UEFA Şampiyonlar Ligi Ön Eleme",
        "UEFA Şampiyonlar Ligi",
        "UEFA Avrupa Ligi Play-Off",
        "UEFA Avrupa Ligi",
        "UEFA Avrupa Konferans Ligi",
        "Trendyol Süper Lig",
        "Ziraat Türkiye Kupası",
        "Basketbol Avrupa Ligi",
        "Euroleague",
    ]

    for comp in competitions:

        if comp.lower() in text.lower():
            competition = comp
            break

    # --------------------------------------------------------
    # KANAL
    # --------------------------------------------------------

    channels = detect_channels(text)

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    if not home_team or not away_team:
        print("[-] Takımlar tespit edilemedi.")
        return None

    if not match_date:
        print("[-] Maç tarihi tespit edilemedi.")
        return None

    if not match_time:
        print("[-] Maç saati tespit edilemedi.")
        return None

    return {
        "home": home_team,
        "away": away_team,
        "date": match_date.isoformat(),
        "time": match_time,
        "competition": competition or "Futbol",
        "channels": channels,
        "url": url,
    }


# ============================================================
# TAKIM SAYFASINDAN MAÇLARI BUL
# ============================================================

def get_fenerbahce_matches():

    print("[*] Fenerbahçe takım sayfası okunuyor...")

    html = get_page(TEAM_URL)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    matches = []

    # Fenerbahçe takım sayfasındaki maç linklerini bul
    for link in soup.find_all("a", href=True):

        href = link.get("href", "")

        if "/home/match/" not in href:
            continue

        match_text = link.get_text(
            " ",
            strip=True
        )

        # Sadece futbol maçlarını hedefliyoruz.
        # Fenerbahçe Beko / kadın basketbolu vb.
        # yanlışlıkla alınmasın.
        if "fenerbahçe" not in match_text.lower():
            continue

        if not href.startswith("http"):
            href = "https://www.sporekrani.com" + href

        print(f"[+] Maç bulundu: {match_text}")
        print(f"    {href}")

        match_data = parse_match_detail(href)

        if match_data:
            matches.append(match_data)

    # Aynı URL birden fazla kez geldiyse temizle
    unique_matches = {}

    for match in matches:
        unique_matches[match["url"]] = match

    return list(unique_matches.values())


# ============================================================
# YAKLAŞAN MAÇI BUL
# ============================================================

def get_next_fenerbahce_match():

    matches = get_fenerbahce_matches()

    if not matches:
        print("[-] Fenerbahçe maçı bulunamadı.")
        return None

    today = date.today()

    upcoming = []

    for match in matches:

        try:
            match_date = date.fromisoformat(
                match["date"]
            )
        except ValueError:
            continue

        if match_date >= today:
            upcoming.append(match)

    if not upcoming:
        print("[-] Yaklaşan Fenerbahçe maçı yok.")
        return None

    upcoming.sort(
        key=lambda x: (
            x["date"],
            x["time"]
        )
    )

    return upcoming[0]


# ============================================================
# BİLDİRİM
# ============================================================

def create_message(match):

    match_date = date.fromisoformat(
        match["date"]
    )

    today = date.today()

    if match_date == today:
        title = "BUGÜN FENERBAHÇEMİZİN MAÇI VAR!"
    else:
        title = "FENERBAHÇEMİZİN YAKLAŞAN MAÇI"

    channels = match["channels"]

    if channels:
        channel_text = " / ".join(channels)
    else:
        channel_text = "Kanal henüz belirtilmemiş"

    message = (
        f"📅 <b>{title}</b>\n\n"
        f"⚽ <b>{match['home']} - {match['away']}</b>\n"
        f"🏆 <i>{match['competition']}</i>\n"
        f"📅 <b>Tarih:</b> {match_date.strftime('%d.%m.%Y')}\n"
        f"⏰ <b>Saat:</b> {match['time']}\n"
        f"📺 <b>Kanal:</b> {channel_text}\n"
    )

    return message


# ============================================================
# ANA KONTROL
# ============================================================

def check_and_notify():

    print("=" * 50)
    print("FENERBAHÇE BOTU ÇALIŞIYOR")
    print("=" * 50)

    match = get_next_fenerbahce_match()

    if not match:
        print("[-] Bildirim gönderilecek maç bulunamadı.")
        return

    print()
    print("[+] Yaklaşan maç:")
    print(
        f"    {match['home']} - {match['away']}"
    )
    print(
        f"    Tarih: {match['date']}"
    )
    print(
        f"    Saat: {match['time']}"
    )
    print(
        f"    Organizasyon: {match['competition']}"
    )
    print(
        f"    Kanal: {', '.join(match['channels']) if match['channels'] else 'Yok'}"
    )

    # --------------------------------------------------------
    # Bildirim anahtarı
    # --------------------------------------------------------

    # Aynı maç için tekrar tekrar bildirim gönderilmesini önler.
    #
    # Kanal sonradan değişirse yeni bildirim gönderebilir.
    channel_key = "|".join(match["channels"])

    notification_key = (
        f"{match['date']}|"
        f"{match['time']}|"
        f"{match['home']}|"
        f"{match['away']}|"
        f"{channel_key}"
    )

    state = load_state()

    notified_matches = state.get(
        "notified_matches",
        []
    )

    if notification_key in notified_matches:

        print()
        print("[*] Bu bilgi daha önce Telegram'a gönderilmiş.")
        print("[*] Yeni bildirim gönderilmeyecek.")

        return

    # --------------------------------------------------------
    # Telegram
    # --------------------------------------------------------

    message = create_message(match)

    print()
    print("[*] Telegram bildirimi gönderiliyor...")

    success = send_telegram_message(message)

    if success:

        notified_matches.append(
            notification_key
        )

        # Son 50 bildirimi tut
        state["notified_matches"] = notified_matches[-50:]

        save_state(state)

        print("[+] Bildirim kaydedildi.")

    print("=" * 50)


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":
    check_and_notify()
