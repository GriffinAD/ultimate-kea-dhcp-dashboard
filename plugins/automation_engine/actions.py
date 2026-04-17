import requests

def webhook_action(action, event, context, manifest):
    # 🔐 enforce security
    context.security.require("automation_engine", manifest, "network_outbound")

    url = action.get("url")
    if not url:
        return
    try:
        requests.post(url, json={
            "event": event.type,
            "payload": event.payload
        }, timeout=5)
    except Exception as e:
        print(f"[AUTOMATION][WEBHOOK] failed: {e}")
