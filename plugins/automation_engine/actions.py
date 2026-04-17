import requests

def webhook_action(action, event, context, manifest):
    # 🔐 enforce security
    context.require_permission("network.outbound")

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
