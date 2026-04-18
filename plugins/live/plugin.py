from core.plugin_api import DashboardPlugin, PluginEvent
from dataclasses import asdict, is_dataclass
import json
import time


class Plugin(DashboardPlugin):
    def register(self, context):
        super().register(context)
        self.subscribers = []

        context.register_route("/api/plugins/live/events", self.stream)
        context.subscribe("*", self.handle_event)

    def handle_event(self, data):
        for sub in list(self.subscribers):
            try:
                sub.append(data)
            except Exception:
                pass

    @staticmethod
    def _serialize_event(event) -> str:
        if isinstance(event, PluginEvent) or is_dataclass(event):
            payload = asdict(event)
        elif isinstance(event, dict):
            payload = event
        else:
            payload = {"raw": str(event)}
        return json.dumps(payload, default=str)

    def stream(self, handler):
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()

        buffer = []
        self.subscribers.append(buffer)

        try:
            while True:
                while buffer:
                    event = buffer.pop(0)
                    handler.wfile.write(
                        f"data: {self._serialize_event(event)}\n\n".encode()
                    )
                    handler.wfile.flush()
                time.sleep(1)
        except Exception:
            pass
        finally:
            self.subscribers.remove(buffer)

        return {"_plugin_handled": True}
