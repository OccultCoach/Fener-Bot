import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    print("[-] Token veya Chat ID eksik!")
    exit(1)

chat_ids = [cid.strip() for cid in CHAT_ID.split(",") if cid.strip()]

# Telegram'dan son mesaj ID'sini çekmek için güncellemeleri al
url_updates = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
resp = requests.get(url_updates).json()

# Son bilinen mesaj ID'sinden geriye doğru tarama aralığı
# Botun son attığı mesajı garantilemek için son 5 ID taranır ve silinir
for cid in chat_ids:
    print(f"[*] {cid} için son mesajlar taranıp siliniyor...")
    
    # Geçici bir referans mesajı atıp ID'sini yakala, sonra onu da sil
    temp_msg = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": cid, "text": "🧹 Temizlik yapılıyor..."}
    ).json()
    
    if temp_msg.get("ok"):
        last_id = temp_msg["result"]["message_id"]
        
        # Son atılan geçici mesaj dahil son 4 mesaj ID'sini silmeyi dene
        for msg_id in range(last_id, last_id - 4, -1):
            del_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
            d_resp = requests.post(del_url, json={"chat_id": cid, "message_id": msg_id}).json()
            if d_resp.get("ok"):
                print(f"[+] Silindi: Mesaj ID {msg_id}")

print("[+] Temizlik tamamlandı.")
