import os
import requests
import json
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

URL = "https://www.sporekrani.com/home/team/fenerbahce"
ISTANBUL = pytz.timezone("Europe/Istanbul")

def send(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
        print("Telegram:", r.status_code)
        if r.status_code != 200:
            print(r.text)
    except Exception as e:
        print("Telegram hatası:", repr(e))

def get_channel(match_url):
    """Maç detay sayfasından yayın kanalını çekmeye çalışır."""
    if not match_url:
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9"
    }

    try:
        r = requests.get(match_url, headers=headers, timeout=20)
        if r.status_code != 200:
            print("Maç detay sayfası:", r.status_code)
            return ""

        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Spor Ekranı sayfasındaki yaygın kanal ifadelerini yakala.
        import re
        patterns = [
            r"(?:hangi kanalda|yayın|tv|kanal)\s*[:\-]?\s*([A-Za-zÇĞİÖŞÜçğıöşü0-9+ .&\-]+)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                channel = m.group(1).strip(" -:|")
                # Çok uzun/yanlış eşleşmeleri ele.
                if 1 <= len(channel) <= 60:
                    return channel

        # Sayfada kanal adı açıkça class/id içinde bulunuyorsa metinsel arama yap.
        keywords = [
            "TRT 1", "TRT Spor", "beIN SPORTS", "beIN Sports",
            "S Sport", "S Sport Plus", "Tivibu Spor", "A Spor",
            "ATV", "Exxen", "Tabii", "DAZN", "CBC Sport"
        ]
        for keyword in keywords:
            if keyword.lower() in text.lower():
                return keyword

    except Exception as e:
        print("Kanal bilgisi alınamadı:", repr(e))

    return ""


def get_matches():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9"
    }
    try:
        r = requests.get(URL, headers=headers, timeout=20)
        print("Spor Ekranı:", r.status_code)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("Bağlantı hatası:", repr(e))
        return []

    matches = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "{}")
        except:
            continue

        graph = data.get("@graph", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for obj in graph:
            if not isinstance(obj, dict) or obj.get("@type") != "SportsEvent":
                continue
            name = obj.get("name", "")
            if "fenerbahçe" not in name.lower():
                continue
            start_date = obj.get("startDate")
            if not start_date:
                continue
            try:
                kick = datetime.fromisoformat(start_date)
                if kick.tzinfo is None:
                    kick = ISTANBUL.localize(kick)
                else:
                    kick = kick.astimezone(ISTANBUL)
            except:
                continue

            home = obj.get("homeTeam", {}).get("name", "") if isinstance(obj.get("homeTeam"), dict) else str(obj.get("homeTeam", ""))
            away = obj.get("awayTeam", {}).get("name", "") if isinstance(obj.get("awayTeam"), dict) else str(obj.get("awayTeam", ""))
            competition = obj.get("organizer", {}).get("name", "") if isinstance(obj.get("organizer"), dict) else ""

            event_id = obj.get("@id") or f"{kick.strftime('%Y%m%d%H%M')}_{home}_{away}"

            # SportsEvent içindeki URL varsa maç detay sayfasını kullan.
            match_url = obj.get("url", "")
            channel = get_channel(match_url)

            matches.append({
                "id": event_id,
                "home": home,
                "away": away,
                "competition": competition,
                "kick": kick,
                "channel": channel
            })

    matches.sort(key=lambda x: x["kick"])
    return matches

def main():
    now = datetime.now(ISTANBUL)
    print("Çalışma zamanı:", now.strftime("%d.%m.%Y %H:%M"))

    matches = get_matches()
    print("Bulunan maç sayısı:", len(matches))

    for m in matches:
        kick = m["kick"]
        minutes_left = (kick - now).total_seconds() / 60
        print(f"{m['home']} - {m['away']} | {kick.strftime('%d.%m %H:%M')} | {minutes_left:.1f} dk")

        # 1. Maç günü bildirimi (sadece sabah saatlerinde)
        if kick.date() == now.date() and 8 <= now.hour <= 11:
            send(
                f"📅 <b>BUGÜN FENERBAHÇE MAÇI VAR!</b>\n\n"
                f"⚽ {m['home']} - {m['away']}\n"
                f"🏆 {m['competition']}\n"
                f"📺 Kanal: {m.get('channel') or 'Kanal bilgisi bulunamadı'}\n"
                f"⏰ Saat: {kick.strftime('%H:%M')}"
            )

        # 2. 30 dakika kala
        if 25 <= minutes_left <= 35:
            send(
                f"🔔 <b>FENERBAHÇE MAÇINA 30 DAKİKA KALDI!</b>\n\n"
                f"⚽ {m['home']} - {m['away']}\n"
                f"🏆 {m['competition']}\n"
                f"📺 Kanal: {m.get('channel') or 'Kanal bilgisi bulunamadı'}\n"
                f"🕐 {kick.strftime('%H:%M')}"
            )

        # 3. Maç başladı
        if -5 <= minutes_left <= 5:
            send(
                f"🟢 <b>FENERBAHÇE MAÇI BAŞLADI!</b>\n\n"
                f"⚽ {m['home']} - {m['away']}\n"
                f"🏆 {m['competition']}\n"
                f"📺 Kanal: {m.get('channel') or 'Kanal bilgisi bulunamadı'}"
            )

if __name__ == "__main__":
    print("Bot çalıştı:", datetime.now(ISTANBUL))
    
    # ===== TEST BİLDİRİMİ (geçici) =====
    send("✅ GitHub Actions test bildirimi geldi! Bot çalışıyor.")
    # ==================================
    
    main()
