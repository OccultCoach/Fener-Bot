import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

# Çıktıların loglarda anında görünmesi için
sys.stdout.reconfigure(line_buffering=True)

# Türkiye Saati (UTC+3)
TURKEY_TZ = timezone(timedelta(hours=3))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

BASE_URL = "https://www.sporekrani.com"
TEAM_URL = f"{BASE_URL}/home/team/fenerbahce/"
STATE_FILE = "bot_state.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

TIMEOUT = 15

MAIN_TV_CHANNELS = [
    "TRT 1",
    "TRT Spor Yıldız",
    "TRT Spor",
    "Tabii Spor",
    "Tabii",
    "beIN Sports Haber",
    "beIN Sports 1",
    "beIN Sports 2",
    "beIN Sports 3",
    "beIN Sports 4",
    "beIN Sports MAX 1",
    "beIN Sports MAX 2",
    "S Sport Plus",
    "S Sport 1",
    "S Sport 2",
    "S Sport",
    "CBC Sport",
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
    "FB TV",
]


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def absolute_url(url):
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/"):
        return BASE_URL + url
    return BASE_URL + "/" + url


def get_page(url):
    print(f"[*] Sayfa okunuyor: {url}", flush=True)
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        print(f"[+] HTTP {response.status_code}", flush=True)
        return response.text
    except requests.RequestException as e:
        print(f"[-] Sayfa alınamadı: {e}", flush=True)
        return None


def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("[-] TELEGRAM_TOKEN veya CHAT_ID eksik.", flush=True)
        return False

    chat_ids = [cid.strip() for cid in CHAT_ID.split(",") if cid.strip()]
    print(f"[*] Toplam {len(chat_ids)} kişiye bildirim gönderilecek...", flush=True)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    success_count = 0

    for cid in chat_ids:
        payload = {
            "chat_id": cid,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            if response.status_code == 200 and data.get("ok"):
                print(f"[+] Telegram bildirimi gönderildi: {cid}", flush=True)
                success_count += 1
            else:
                print(f"[-] Telegram API hatası ({cid}): {data}", flush=True)
        except requests.RequestException as e:
            print(f"[-] Telegram ağ hatası ({cid}): {e}", flush=True)

    return success_count > 0


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"notified_matches": [], "next_match_date": None}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        if not isinstance(state, dict):
            return {"notified_matches": [], "next_match_date": None}
        state.setdefault("notified_matches", [])
        state.setdefault("next_match_date", None)
        return state
    except Exception as e:
        print(f"[-] State dosyası okunamadı: {e}", flush=True)
        return {"notified_matches": [], "next_match_date": None}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        print("[+] State dosyası güncellendi.", flush=True)
    except Exception as e:
        print(f"[-] State dosyası kaydedilemedi: {e}", flush=True)


def canonical_channel_name(channel):
    normalized = (
        channel.lower()
        .replace(" ", "")
        .replace(".", "")
        .replace(",", "")
    )
    mapping = {
        "beinsports1": "beIN Sports 1",
        "beinsports2": "beIN Sports 2",
        "beinsports3": "beIN Sports 3",
        "beinsports4": "beIN Sports 4",
        "beinsportsmax1": "beIN Sports MAX 1",
        "beinsportsmax2": "beIN Sports MAX 2",
        "beinsportshaber": "beIN Sports Haber",
        "tv85": "TV8,5",
        "sporsmart": "Spor Smart",
    }
    return mapping.get(normalized, channel)


def detect_channels(text):
    text = normalize_text(text)
    detected = []
    channels_sorted = sorted(MAIN_TV_CHANNELS, key=len, reverse=True)

    for channel in channels_sorted:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(channel) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            canonical = canonical_channel_name(channel)
            if canonical not in detected:
                detected.append(canonical)
    return detected


def extract_broadcast_section(soup):
    for tag in soup.find_all(["p", "div", "section", "article"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if not text or len(text) > 1000:
            continue
        lower = text.lower()
        if "kanallarından" in lower or "kanalından" in lower:
            return text

    for tag in soup.find_all(["p", "div", "section", "article"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if not text or len(text) > 700:
            continue
        lower = text.lower()
        if any(w in lower for w in ("canlı izle", "canlı yayın", "hangi kanalda", "yayın")):
            channels = detect_channels(text)
            if channels:
                return text
    return None


TURKISH_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}


def parse_date_from_text(text):
    pattern = r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})\b"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    day = int(match.group(1))
    month = TURKISH_MONTHS.get(match.group(2).lower())
    year = int(match.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_time_from_text(text):
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not match:
        return None
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def detect_competition(text):
    competitions = [
        "UEFA Şampiyonlar Ligi Play-Off",
        "UEFA Şampiyonlar Ligi Ön Eleme",
        "UEFA Şampiyonlar Ligi",
        "UEFA Avrupa Ligi Play-Off",
        "UEFA Avrupa Ligi",
        "UEFA Konferans Ligi",
        "UEFA Avrupa Konferans Ligi",
        "Trendyol Süper Lig",
        "Süper Lig",
        "Ziraat Türkiye Kupası",
        "Türkiye Kupası",
    ]
    lower_text = text.lower()
    for competition in competitions:
        if competition.lower() in lower_text:
            return competition
    return "Futbol"


def parse_teams_from_match_page(soup):
    candidates = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = normalize_text(tag.get_text(" ", strip=True))
        if text:
            candidates.append(text)

    if soup.title:
        title_text = normalize_text(soup.title.get_text(" ", strip=True))
        if title_text:
            candidates.append(title_text)

    for text in candidates:
        cleaned_text = re.sub(
            r"\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        match = re.search(
            r"(.+?)\s+(?:-|–|—|vs)\s+(.+?)(?:\s+maçı|\s+h?angi kanalda.*)?$",
            cleaned_text,
            flags=re.IGNORECASE,
        )
        if match:
            home = normalize_text(match.group(1))
            away = normalize_text(match.group(2))
            away = re.sub(r"\s+maçı.*$", "", away, flags=re.IGNORECASE).strip()
            if 1 <= len(home) <= 60 and 1 <= len(away) <= 60 and "spor ekranı" not in home.lower():
                return home, away

    return None, None


def parse_match_detail(url):
    html = get_page(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    full_text = normalize_text(soup.get_text(" ", strip=True))

    home_team, away_team = parse_teams_from_match_page(soup)
    if not home_team or not away_team:
        print("[-] Takımlar tespit edilemedi.", flush=True)
        return None

    combined_teams = f"{home_team} {away_team}".lower()
    if "fenerbahçe" not in combined_teams:
        print("[-] Bu sayfa Fenerbahçe maçı değil.", flush=True)
        return None

    match_date = parse_date_from_text(full_text)
    if not match_date:
        print("[-] Maç tarihi bulunamadı.", flush=True)
        return None

    match_time = parse_time_from_text(full_text)
    if not match_time:
        print("[-] Maç saati bulunamadı.", flush=True)
        return None

    competition = detect_competition(full_text)
    broadcast_section = extract_broadcast_section(soup)

    if broadcast_section:
        print(f"[+] Yayın bölümü bulundu: {broadcast_section}", flush=True)
        channels = detect_channels(broadcast_section)
    else:
        print("[-] Yayın bölümü bulunamadı.", flush=True)
        channels = []

    return {
        "home": home_team,
        "away": away_team,
        "date": match_date.isoformat(),
        "time": match_time,
        "competition": competition,
        "channels": channels,
        "url": url,
    }


def get_match_links():
    html = get_page(TEAM_URL)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "/home/match/" not in href:
            continue
        href = absolute_url(href)
        if href not in links:
            links.append(href)

    print(f"[+] {len(links)} adet maç linki bulundu.", flush=True)
    return links


def get_next_fenerbahce_match():
    links = get_match_links()
    if not links:
        print("[-] Maç linki bulunamadı.", flush=True)
        return None

    matches = []
    for link in links:
        match = parse_match_detail(link)
        if match:
            matches.append(match)

    if not matches:
        print("[-] Fenerbahçe maçı bulunamadı.", flush=True)
        return None

    today = datetime.now(TURKEY_TZ).date()
    upcoming = []

    for match in matches:
        try:
            match_date = date.fromisoformat(match["date"])
        except ValueError:
            continue
        if match_date >= today:
            upcoming.append(match)

    if not upcoming:
        print("[-] Yaklaşan Fenerbahçe maçı bulunamadı.", flush=True)
        return None

    upcoming.sort(key=lambda m: (m["date"], m["time"]))
    return upcoming[0]


def create_notification_key(match):
    channels = "|".join(sorted(match["channels"]))
    return (
        f"{match['date']}|"
        f"{match['time']}|"
        f"{match['home']}|"
        f"{match['away']}|"
        f"{channels}"
    )


def create_message(match, notification_type="UPCOMING"):
    match_date = date.fromisoformat(match["date"])

    if notification_type == "STARTING_SOON":
        title = "⏳ FENERBAHÇEMİZİN MAÇI BAŞLAMAK ÜZERE!"
    elif notification_type == "MATCHDAY":
        title = "BUGÜN FENERBAHÇEMİZİN MAÇI VAR!"
    else:
        title = "FENERBAHÇEMİZİN YAKLAŞAN MAÇI"

    if match["channels"]:
        channel_text = " / ".join(match["channels"])
    else:
        channel_text = "Henüz belirtilmemiş"

    return (
        f"📅 <b>{title}</b>\n\n"
        f"⚽️ <b>{match['home']} - {match['away']}</b>\n"
        f"🏆 <i>{match['competition']}</i>\n"
        f"📅 <b>Tarih:</b> {match_date.strftime('%d.%m.%Y')}\n"
        f"⏰ <b>Saat:</b> {match['time']}\n"
        f"📺 <b>Kanal:</b> {channel_text}"
    )


def check_and_notify():
    print("=" * 60, flush=True)
    print("FENERBAHÇE BOTU ÇALIŞIYOR", flush=True)
    print("=" * 60, flush=True)

    now_tr = datetime.now(TURKEY_TZ)
    today_str = now_tr.date().isoformat()
    state = load_state()

    # Akşam kontrollerinde gereksiz sorgu engeli:
    # Eğer sabahki kontrolde sıradaki maçın bugün olmadığı kesinleştiyse, web sitesine istek atmadan çık.
    next_match_date = state.get("next_match_date")
    if now_tr.hour >= 12 and next_match_date and next_match_date != today_str:
        print(f"[*] Bugün ({today_str}) maç günü değil. Sıradaki maç tarihi: {next_match_date}", flush=True)
        print("[*] Web sitesi taranmayacak. İşlem 1 saniyede tamamlandı.", flush=True)
        print("=" * 60, flush=True)
        return

    match = get_next_fenerbahce_match()
    if not match:
        print("[-] İşlenecek maç bulunamadı.", flush=True)
        return

    print(
        f"\n[+] Yaklaşan maç:\n"
        f"    {match['home']} - {match['away']}\n"
        f"    Tarih: {match['date']}\n"
        f"    Saat: {match['time']}\n"
        f"    Organizasyon: {match['competition']}",
        flush=True,
    )

    channel_log = ", ".join(match["channels"]) if match["channels"] else "Belirtilmemiş"
    print(f"    Kanal: {channel_log}\n    URL: {match['url']}", flush=True)

    # Sıradaki maçın tarihini state'e kaydet
    state["next_match_date"] = match["date"]

    base_key = create_notification_key(match)
    notified_matches = state.get("notified_matches", [])

    match_dt_str = f"{match['date']} {match['time']}"
    match_dt = datetime.strptime(match_dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=TURKEY_TZ)

    time_diff_minutes = (match_dt - now_tr).total_seconds() / 60
    is_today = (match["date"] == today_str)

    print(f"[*] Şu anki Türkiye Saati: {now_tr.strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"[*] Maça kalan süre: {time_diff_minutes:.1f} dakika", flush=True)

    # 1. Kontrol: Maça 0 ile 20 dakika arası mı kaldı? (15 dk kala uyarısı)
    if is_today and 0 <= time_diff_minutes <= 20:
        target_key = f"SOON|{base_key}"
        notification_type = "STARTING_SOON"
    # 2. Kontrol: Maç günü sabahı mı?
    elif is_today:
        target_key = f"MATCHDAY|{base_key}"
        notification_type = "MATCHDAY"
    # 3. Kontrol: Fikstüre yeni giren maç bildirimi
    else:
        target_key = base_key
        notification_type = "UPCOMING"

    if target_key in notified_matches:
        print(f"\n[*] Bu bildirim daha önce gönderilmiş ({target_key}).\n[*] Yeni Telegram bildirimi gönderilmeyecek.", flush=True)
        save_state(state)
        return

    print(f"\n[*] Yeni bildirim türü: {notification_type}", flush=True)
    print("[*] Telegram bildirimi gönderiliyor...", flush=True)

    message = create_message(match, notification_type=notification_type)
    success = send_telegram_message(message)

    if not success:
        print("[-] Telegram gönderimi başarısız.", flush=True)
        return

    notified_matches.append(target_key)
    state["notified_matches"] = notified_matches[-100:]
    save_state(state)
    print("[+] Bildirim state'e kaydedildi.\n" + "=" * 60, flush=True)


if __name__ == "__main__":
    check_and_notify()
