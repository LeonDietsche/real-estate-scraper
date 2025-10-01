import os, requests
WA_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3000/send-message")

def send_whatsapp_message(message: str, jid: str):
    if not jid:
        print("❌ WhatsApp JID missing (got empty/None)."); return
    r = requests.post(WA_URL, json={"jid": jid, "message": message}, timeout=15)
    if r.status_code >= 400:
        print(f"❌ WA HTTP {r.status_code}: {r.text[:400]}")
    r.raise_for_status()
    print(f"📤 Message sent to {jid}")