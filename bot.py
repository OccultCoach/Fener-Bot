import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(line_buffering=True)

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

CHANNEL_PRIORITY = [
    "TRT 1", "TRT Spor", "TRT Spor Yıldız", "TV8,5", "TV8.5", "TV8", "ATV", "A Spor",
    "Tabii Spor", "Tabii", "beIN Sports 1", "beIN Sports 2", "beIN Sports 3", "beIN Sports 4",
    "beIN Sports MAX 1", "beIN Sports MAX 2", "beIN Sports Haber", "S Sport", "S Sport 1",
    "S Sport 2", "S Sport Plus", "Exxen", "Tivibu Spor 1", "Tivibu Spor 2", "Tivibu Spor",
    "Smart Spor 1", "Smart Spor 2", "Smart Spor", "Spor Smart", "FB TV", "CBC Sport",
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
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        print(f"[+] HTTP {response.status_code}", flush=True)
        return response.text
    except requests.RequestException as e:
        print(f"[-] Sayfa alınamadı: {e}", flush=True)
        return None


def send_telegram_message(message, reply_markup=None):
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
        if reply_markup:
            payload["reply_markup"] = reply_markup

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
    default_state = {"notified_matches": []}
    if not os.path.exists(STATE_FILE):
        return default_state
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)
        if not isinstance(state, dict):
            return default_state
        state.setdefault("notified_matches", [])
        return state
    except Exception as e:
        print(f"[-] State dosyası okunamadı: {e}", flush=True)
        return default_state


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
        print("[+] State dosyası güncellendi.", flush=True)
    except Exception as e:
        print(f"[-] State dosyası kaydedilemedi: {e}", flush=True)


def canonical_channel_name(channel):
    normalized = channel.lower().replace(" ", "").replace(".", "").replace(",", "")
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
    channels_sorted = sorted(CHANNEL_PRIORITY, key=len, reverse=True)

    for channel in channels_sorted:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(channel) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            canonical = canonical_channel_name(channel)
            if canonical not in detected:
                detected.append(canonical)
    
    def get_priority(ch):
        try:
            return CHANNEL_PRIORITY.index(ch)
        except ValueError:
            return 999

    return sorted(detected, key=get_priority)


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


def detect_competition(target_text):
    competitions = [
        "UEFA Şampiyonlar Ligi Play-Off",
        "UEFA Şampiyonlar Ligi Ön Eleme",
        "UEFA Şampiyonlar Ligi",
        "UEFA Avrupa Ligi Play-Off",
        "UEFA Avrupa Ligi",
        "UEFA Konferans Ligi",
        "Trendyol Süper Lig",
        "Süper Lig",
        "Ziraat Türkiye Kupası",
        "Türkiye Kupası",
        "Süper Kupa",
    ]
    for comp in competitions:
        pattern = r"(?i)\b" + re.escape(comp) + r"\b"
        if re.search(pattern, target_text):
            return comp
    return "Futbol Müsabakası"


def is_football_match(url, title_text):
    combined = f"{url} {title_text}".lower()
    non_football_keywords = [
        "basketbol", "euroleague", "voleybol",
        "sultanlar-ligi", "efeler-ligi", "kadinlar-basketbol",
    ]
    return not any(keyword in combined for keyword in non_football_keywords)


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
        cleaned = re.sub(r"\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}", "", text, flags=re.IGNORECASE).strip()
        match = re.search(r"(.+?)\s+(?:-|–|—|vs)\s+(.+?)(?:\s+maçı|\s+h?angi kanalda.*)?$", cleaned, flags=re.IGNORECASE)
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
    title_text = soup.title.get_text(" ", strip=True) if soup.title else ""
    full_text = normalize_text(soup.get_text(" ", strip=True))

    if not is_football_match(url, title_text):
        print(f"[-] Futbol dışı branş atlandı: {url}", flush=True)
        return None

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

    broadcast_section = extract_broadcast_section(soup)
    target_comp_text = f"{url} {title_text} {broadcast_section or ''}"
    competition = detect_competition(target_comp_text)

    if broadcast_section:
        channels = detect_channels(broadcast_section)
    else:
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
        if "/home/match/" in href:
            full_link = absolute_url(href)
            if full_link not in links:
                links.append(full_link)

    print(f"[+] {len(links)} adet maç linki bulundu.", flush=True)
    return links


def get_upcoming_matches_from_web():
    links = get_match_links()
    if not links:
        return []

    matches = []
    for link in links:
        match = parse_match_detail(link)
        if match:
            matches.append(match)

    matches.sort(key=lambda m: (m["date"], m["time"]))
    return matches


def get_espn_matches(dates_to_check):
    """
    ESPN'den belirtilen tarihlerdeki maçları çeker.
    """
    leagues = ["uefa.champions", "tur.1", "uefa.europa", "uefa.europa.conf"]
    results = []

    for d in dates_to_check:
        date_str = d.strftime("%Y%m%d")
        for league in leagues:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={date_str}"
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                events = data.get("events", [])
                for ev in events:
                    comp = ev.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    team_names = [c.get("team", {}).get("displayName", "").lower() for c in competitors]
                    
                    if any("fenerbah" in name for name in team_names):
                        results.append(ev)
            except Exception as e:
                print(f"[-] ESPN {league} ({date_str}) hatası: {e}", flush=True)

    return results


def parse_espn_event(event):
    try:
        comp = event.get("competitions", [{}])[0]
        status = event.get("status", {})
        status_type = status.get("type", {})
        is_finished = bool(status_type.get("completed", False))

        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None, False, None

        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        home_name = home_comp.get("team", {}).get("displayName", "")
        home_score = home_comp.get("score", "")
        away_name = away_comp.get("team", {}).get("displayName", "")
        away_score = away_comp.get("score", "")

        score_text = None
        if home_score != "" and away_score != "":
            score_text = f"{home_name} {home_score} - {away_score} {away_name}"

        date_str = event.get("date", "")
        match_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(TURKEY_TZ)
        league_name = event.get("league", {}).get("name", "Futbol Müsabakası")

        parsed_match = {
            "home": home_name,
            "away": away_name,
            "date": match_dt.date().isoformat(),
            "time": match_dt.strftime("%H:%M"),
            "competition": league_name,
            "channels": [],
            "url": BASE_URL,
            "match_dt": match_dt,
        }
        return parsed_match, is_finished, score_text
    except Exception as e:
        print(f"[-] ESPN ayrıştırma hatası: {e}", flush=True)
        return None, False, None


def get_highlights_url(match):
    competition = match.get("competition", "")
    home = match.get("home", "")
    away = match.get("away", "")
    match_year = match.get("date", "").split("-")[0]
    
    if "Süper Lig" in competition or "Türkiye Kupası" in competition:
        search_query = f"{home} {away} {match_year} maç özeti beIN SPORTS Türkiye"
    else:
        search_query = f"{home} {away} {match_year} maç özeti TRT Spor Tabii Spor"
        
    encoded_query = requests.utils.quote(search_query)
    return f"https://www.youtube.com/results?search_query={encoded_query}"


def create_notification_key(match):
    channels = "|".join(match.get("channels", []))
    return (
        f"{match['date']}|"
        f"{match['time']}|"
        f"{match['home']}|"
        f"{match['away']}|"
        f"{channels}"
    )


def create_message(match, notification_type="UPCOMING", score=None):
    match_date = date.fromisoformat(match["date"])
    channel_text = " / ".join(match["channels"]) if match.get("channels") else "Henüz belirtilmemiş"

    if notification_type == "STARTING_SOON":
        return (
            f"🔥 🔵 <b>MAÇ BAŞLAMAK ÜZERE!</b> 🟡 🔥\n\n"
            f"⚽️ <b>{match['home']} - {match['away']}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n"
            f"⏰ <b>Saat:</b> {match['time']}\n"
            f"📺 <b>Kanal:</b> {channel_text}\n\n"
            f"💛💙 <i>Haydi Fenerbahçeli! Ekran başına geçme zamanı.</i>"
        )

    if notification_type == "MATCH_ENDED":
        match_title = score if score else f"{match['home']} - {match['away']}"
        return (
            f"🏁 💛 <b>MAÇ SONA ERDİ!</b> 💙 🎉\n\n"
            f"⚽️ <b>{match_title}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n\n"
            f"🟡🔵 Karşılaşma tamamlandı! Maçın özeti ve golleri için butona basınız."
        )

    if notification_type == "MATCHDAY":
        return (
            f"📣 🟡 <b>BUGÜN FENERBAHÇEMİZİN MAÇI VAR!</b> 🔵\n\n"
            f"⚽️ <b>{match['home']} - {match['away']}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n"
            f"📅 <b>Tarih:</b> {match_date.strftime('%d.%m.%Y')}\n"
            f"⏰ <b>Saat:</b> {match['time']}\n"
            f"📺 <b>Kanal:</b> {channel_text}"
        )

    return (
        f"📅 🟡 <b>FENERBAHÇEMİZİN YAKLAŞAN MAÇI</b> 🔵\n\n"
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
    today_date = now_tr.date()
    yesterday_date = today_date - timedelta(days=1)
    today_str = today_date.isoformat()

    state = load_state()
    notified_matches = state.get("notified_matches", [])

    # ADIM 1: ESPN'den dün ve bugünün maçlarını tara
    print(f"[*] ESPN Canlı Skor taranıyor (Dün: {yesterday_date}, Bugün: {today_date})...", flush=True)
    espn_events = get_espn_matches([yesterday_date, today_date])
    
    for ev in espn_events:
        parsed_match, is_finished, score_data = parse_espn_event(ev)
        if not parsed_match:
            continue

        match_dt = parsed_match["match_dt"]
        time_diff = (match_dt - now_tr).total_seconds() / 60

        print(f"[+] ESPN maçı bulundu: {parsed_match['home']} - {parsed_match['away']} (Fark: {time_diff:.1f} dk, Bitti mi: {is_finished})", flush=True)

        # Son 6 saat içinde başlamış bir maç
        if -360 <= time_diff <= 0:
            ended_key = f"ENDED|{parsed_match['date']}|{parsed_match['time']}|{parsed_match['home']}|{parsed_match['away']}"
            
            if is_finished and ended_key not in notified_matches:
                print(f"[+] Gönderilecek maç sonu bulundu: {parsed_match['home']} vs {parsed_match['away']} (Skor: {score_data})", flush=True)
                msg = create_message(parsed_match, notification_type="MATCH_ENDED", score=score_data)
                highlights_url = get_highlights_url(parsed_match)
                reply_markup = {"inline_keyboard": [[{"text": "▶️ Maç Özeti & Golleri İzle", "url": highlights_url}]]}
                
                success = send_telegram_message(msg, reply_markup=reply_markup)
                if success:
                    notified_matches.append(ended_key)
                    state["notified_matches"] = notified_matches[-100:]
                    save_state(state)
                    print("[+] Maç sonu bildirimi gönderildi.\n" + "=" * 60, flush=True)
                    return

    # ADIM 2: Yaklaşan Maç Kontrolü (Sporekrani.com)
    web_matches = get_upcoming_matches_from_web()
    if not web_matches:
        print("[-] Fikstürde yaklaşan maç bulunamadı.", flush=True)
        return

    match = web_matches[0]
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

    base_key = create_notification_key(match)
    match_dt_str = f"{match['date']} {match['time']}"
    match_dt = datetime.strptime(match_dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=TURKEY_TZ)
    time_diff_minutes = (match_dt - now_tr).total_seconds() / 60

    print(f"[*] Şu anki Türkiye Saati: {now_tr.strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"[*] Maç başlangıcına göre fark: {time_diff_minutes:.1f} dakika", flush=True)

    if 0 <= time_diff_minutes <= 15:
        target_key = f"SOON|{base_key}"
        notification_type = "STARTING_SOON"
    elif match["date"] == today_str:
        target_key = f"MATCHDAY|{base_key}"
        notification_type = "MATCHDAY"
    else:
        target_key = base_key
        notification_type = "UPCOMING"

    if target_key in notified_matches:
        print(f"\n[*] Bu bildirim daha önce gönderilmiş ({target_key}).\n[*] Yeni Telegram bildirimi gönderilmeyecek.", flush=True)
        save_state(state)
        return

    print(f"\n[*] Yeni bildirim türü: {notification_type}", flush=True)
    print("[*] Telegram bildirimi gönderiliyor...", flush=True)

    keyboard_buttons = []
    if notification_type in ("STARTING_SOON", "UPCOMING"):
        keyboard_buttons.append([{"text": "📺 Maç Detayı & Kanallar", "url": match["url"]}])

    reply_markup = {"inline_keyboard": keyboard_buttons} if keyboard_buttons else None
    message = create_message(match, notification_type=notification_type)
    success = send_telegram_message(message, reply_markup=reply_markup)

    if success:
        notified_matches.append(target_key)
        state["notified_matches"] = notified_matches[-100:]
        save_state(state)
        print("[+] Bildirim state'e kaydedildi.\n" + "=" * 60, flush=True)


if __name__ == "__main__":
    check_and_notify()
