import requests

WHATSAPP_API_URL = "http://localhost:3000/send-message"

def send_whatsapp_message(message: str, jid: str):

    payload = {
        "jid": jid,
        "message": message
    }

    try:
        response = requests.post(WHATSAPP_API_URL, json=payload)
        response.raise_for_status()
        print(f"📤 Message sent to {jid}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send WhatsApp message: {e}")
