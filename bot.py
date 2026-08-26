import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

# Logların anında GitHub Actions konsoluna dökülmesi için
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

# Türkiye Resmi / Esas Yayıncı Öncelik Sıralaması
CHANNEL_PRIORITY = [
    # Türkiye Ulusal & Açık Kanallar
    "TRT 1",
    "TRT Spor",
    "TRT Spor Yıldız",
    "TV8,5",
    "TV8.5",
    "TV8",
    "ATV",
    "A Spor",
    # Türkiye Resmi Dijital & Platform Yayıncıları
    "Tabii Spor",
    "Tabii",
    "beIN Sports 1",
    "beIN Sports 2",
    "beIN Sports 3",
    "beIN Sports 4",
    "beIN Sports MAX 1",
    "beIN Sports MAX 2",
    "beIN Sports Haber",
    "S Sport",
    "S Sport 1",
    "S Sport 2",
    "S Sport Plus",
    "Exxen",
    "Tivibu Spor 1",
    "Tivibu Spor 2",
    "Tivibu Spor",
    "Smart Spor 1",
    "Smart Spor 2",
    "Smart Spor",
    "Spor Smart",
    "FB TV",
    # Yabancı / Uydu Yayıncılar
    "CBC Sport",
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
    default_state = {"notified_matches": [], "last_match_date": None}
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


def sort_channels_by_priority(channels):
    def get_priority(ch):
        try:
            return CHANNEL_PRIORITY.index(ch)
        except ValueError:
            return 999
    return sorted(channels, key=get_priority)


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
    
    return sort_channels_by_priority(detected)


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
        "UEFA Avrupa Konferans Ligi",
        "UEFA Konferans Ligi",
        "Trendyol Süper Lig",
        "Süper Lig",
        "Ziraat Türkiye Kupası",
        "Türkiye Kupası",
        "Süper Kupa",
    ]
    for comp in competitions:
        pattern = r"\b" + re.escape(comp) + r"\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return comp
    return "Futbol Müsabakası"


def is_football_match(url, title_text):
    combined = f"{url} {title_text}".lower()
    non_football_keywords = [
        "basketbol",
        "euroleague",
        "voleybol",
        "sultanlar-ligi",
        "efeler-ligi",
        "kadinlar-basketbol",
    ]
    if any(keyword in combined for keyword in non_football_keywords):
        return False
    return True


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


def get_recent_fotmob_matches():
    """
    FotMob API'den Fenerbahçe'nin son oynanan veya devam eden maçlarını çeker.
    """
    try:
        team_url = "https://www.fotmob.com/api/teams?id=8695"
        resp = requests.get(team_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        
        fixtures = resp.json().get("fixtures", {}).get("allFixtures", {}).get("fixtures", [])
        return fixtures
    except Exception as e:
        print(f"[-] FotMob maç listesi alınamadı: {e}", flush=True)
        return []


def get_fotmob_match_details(match_id):
    try:
        detail_url = f"https://www.fotmob.com/api/matchDetails?matchId={match_id}"
        resp = requests.get(detail_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None, False, None

        m_data = resp.json()
        header = m_data.get("header", {})
        status_info = header.get("status", {})
        is_finished = bool(status_info.get("finished", False) or status_info.get("cancelled", False))
        
        score_text = None
        teams = header.get("teams", [])
        if len(teams) >= 2:
            home_team = teams[0].get("name", "")
            home_score = teams[0].get("score", "")
            away_team = teams[1].get("name", "")
            away_score = teams[1].get("score", "")
            if home_score != "" and away_score != "":
                score_text = f"{home_team} {home_score} - {away_score} {away_team}"

        # Kadro
        content = m_data.get("content", {})
        lineup_data = content.get("lineup", {})
        lineup_roles = None
        
        if lineup_data and lineup_data.get("lineup"):
            # Fenerbahçe indexini bul
            home_name = teams[0].get("name", "").lower() if teams else ""
            is_fb_home = "fenerbah" in home_name
            team_lineup = lineup_data.get("lineup", [])[0 if is_fb_home else 1]

            if team_lineup and team_lineup.get("players"):
                roles = {"GK": [], "DF": [], "MF": [], "FW": []}
                for row in team_lineup.get("players", []):
                    for p in row:
                        name = p.get("name", {}).get("fullName") or p.get("name", {}).get("lastName", "")
                        role = p.get("role", "MF")
                        if role in roles:
                            roles[role].append(name)
                        else:
                            roles["MF"].append(name)

                if sum(len(v) for v in roles.values()) == 11:
                    lineup_roles = roles

        return lineup_roles, is_finished, score_text
    except Exception as e:
        print(f"[-] FotMob maç detayı alınamadı: {e}", flush=True)
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


def create_message(match, notification_type="UPCOMING", lineup=None, score=None):
    match_date = date.fromisoformat(match["date"])
    channel_text = " / ".join(match["channels"]) if match.get("channels") else "Henüz belirtilmemiş"

    # 1. Maça Başlamak Üzere & İlk 11 (Birleşik Mesaj)
    if notification_type == "STARTING_SOON":
        lineup_block = ""
        if lineup:
            gk_text = ", ".join(lineup.get("GK", []))
            df_text = ", ".join(lineup.get("DF", []))
            mf_text = ", ".join(lineup.get("MF", []))
            fw_text = ", ".join(lineup.get("FW", []))
            lineup_block = (
                f"📋 <b>İLK 11'İMİZ:</b>\n"
                f"🧤 <b>Kaleci:</b> {gk_text}\n"
                f"🛡 <b>Defans:</b> {df_text}\n"
                f"⚙️ <b>Orta Saha:</b> {mf_text}\n"
                f"⚡️ <b>Hücum:</b> {fw_text}\n\n"
            )

        return (
            f"🔥 🔵 <b>MAÇ BAŞLAMAK ÜZERE!</b> 🟡 🔥\n\n"
            f"{lineup_block}"
            f"⚽️ <b>{match['home']} - {match['away']}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n"
            f"⏰ <b>Saat:</b> {match['time']}\n"
            f"📺 <b>Kanal:</b> {channel_text}\n\n"
            f"💛💙 <i>Haydi Fenerbahçeli! Ekran başına geçme zamanı.</i>"
        )

    # 2. Maç Sona Erdiğinde (Nihai Skorlu)
    if notification_type == "MATCH_ENDED":
        match_title = score if score else f"{match['home']} - {match['away']}"
        return (
            f"🏁 💛 <b>MAÇ SONA ERDİ!</b> 💙 🎉\n\n"
            f"⚽️ <b>{match_title}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n\n"
            f"🟡🔵 Karşılaşma tamamlandı! Maçın özeti ve golleri için butona basınız."
        )

    # 3. Sabah / Günlük Bildirim (MATCHDAY)
    if notification_type == "MATCHDAY":
        return (
            f"📣 🟡 <b>BUGÜN FENERBAHÇEMİZİN MAÇI VAR!</b> 🔵\n\n"
            f"⚽️ <b>{match['home']} - {match['away']}</b>\n"
            f"🏆 <i>{match['competition']}</i>\n"
            f"📅 <b>Tarih:</b> {match_date.strftime('%d.%m.%Y')}\n"
            f"⏰ <b>Saat:</b> {match['time']}\n"
            f"📺 <b>Kanal:</b> {channel_text}"
        )

    # 4. Gelecek Maç Bilgisi
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
    today_str = now_tr.date().isoformat()
    state = load_state()
    notified_matches = state.get("notified_matches", [])

    # ADIM 1: FotMob üzerinden son biten maçın durumunu kontrol et (Web'den silinse bile yakalar)
    fotmob_fixtures = get_recent_fotmob_matches()
    for fix in fotmob_fixtures:
        fix_utc_str = fix.get("status", {}).get("utcTime", "")
        if not fix_utc_str:
            continue
        try:
            utc_dt = datetime.fromisoformat(fix_utc_str.replace("Z", "+00:00"))
            match_dt = utc_dt.astimezone(TURKEY_TZ)
        except Exception:
            continue

        time_diff = (match_dt - now_tr).total_seconds() / 60
        
        # Eğer maç başlamış ve üzerinden en fazla 3.5 saat geçmişse:
        if -220 <= time_diff <= 0:
            match_id = fix.get("id")
            lineup_data, is_finished, score_data = get_fotmob_match_details(match_id)
            
            home_name = fix.get("home", {}).get("name", "Ev Sahibi")
            away_name = fix.get("away", {}).get("name", "Deplasman")
            comp_name = fix.get("tournament", {}).get("name", "Futbol Müsabakası")

            recent_match = {
                "home": home_name,
                "away": away_name,
                "date": match_dt.date().isoformat(),
                "time": match_dt.strftime("%H:%M"),
                "competition": comp_name,
                "channels": [],
                "url": BASE_URL,
            }
            ended_key = f"ENDED|{recent_match['date']}|{recent_match['time']}|{recent_match['home']}|{recent_match['away']}"
            
            if is_finished and ended_key not in notified_matches:
                print(f"[+] Son biten maç tespit edildi: {home_name} vs {away_name}", flush=True)
                msg = create_message(recent_match, notification_type="MATCH_ENDED", score=score_data)
                highlights_url = get_highlights_url(recent_match)
                reply_markup = {"inline_keyboard": [[{"text": "▶️ Maç Özeti & Golleri İzle", "url": highlights_url}]]}
                
                success = send_telegram_message(msg, reply_markup=reply_markup)
                if success:
                    notified_matches.append(ended_key)
                    state["notified_matches"] = notified_matches[-100:]
                    save_state(state)
                    print("[+] Maç sonu bildirimi gönderildi ve kaydedildi.", flush=True)
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

    # 1. Maça Başlamak Üzere & İlk 11 (0 - 15 dk kala)
    if 0 <= time_diff_minutes <= 15:
        target_key = f"SOON|{base_key}"
        notification_type = "STARTING_SOON"
        lineup_data, _, _ = get_fotmob_match_details(match.get("id"))
        lineup = lineup_data
    # 2. Maç Günü Sabahı
    elif match["date"] == today_str:
        target_key = f"MATCHDAY|{base_key}"
        notification_type = "MATCHDAY"
        lineup = None
    # 3. Gelecek Yaklaşan Maç
    else:
        target_key = base_key
        notification_type = "UPCOMING"
        lineup = None

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
    message = create_message(match, notification_type=notification_type, lineup=lineup)
    success = send_telegram_message(message, reply_markup=reply_markup)

    if success:
        notified_matches.append(target_key)
        state["notified_matches"] = notified_matches[-100:]
        save_state(state)
        print("[+] Bildirim state'e kaydedildi.\n" + "=" * 60, flush=True)


if __name__ == "__main__":
    check_and_notify()
