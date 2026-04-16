from lib.plugin_system import DashboardPlugin
import requests

class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.nodes = {
            "kea1": "http://127.0.0.1:8000",
        }

        context.register_route(
            "/api/plugins/kea-ha/status",
            self.get_status
        )

    def get_status(self, handler=None):
        result = {}
        for name, url in self.nodes.items():
            try:
                r = requests.post(url, json={
                    "command": "ha-status",
                    "service": ["dhcp4"]
                }, timeout=2)
                result[name] = r.json()
            except Exception as e:
                result[name] = {"error": str(e)}
        return result

    def start(self):
        pass

    def stop(self):
        pass
