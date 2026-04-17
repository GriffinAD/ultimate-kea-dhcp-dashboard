from lib.plugin_system import DashboardPlugin
import requests

class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.webhook_url = context.config.get("home_assistant_webhook")

        # API endpoint to manually trigger test notification
        context.register_route(
            "/api/plugins/home-assistant/test",
            self.send_test
        )

        # Subscribe to HA events (future use)
        context.event_bus.subscribe("kea.ha.status", self.handle_ha_status)

    def send_test(self, handler=None):
        payload = {
            "event": "test",
            "message": "Home Assistant plugin test successful"
        }
        return self._send(payload)

    def handle_ha_status(self, data):
        payload = {
            "event": "kea_ha_status",
            "data": data
        }
        self._send(payload)

    def _send(self, payload):
        if not self.webhook_url:
            return {"error": "No webhook configured"}

        try:
            r = requests.post(self.webhook_url, json=payload, timeout=2)
            return {"status": r.status_code}
        except Exception as e:
            return {"error": str(e)}

    def start(self):
        pass

    def stop(self):
        pass
