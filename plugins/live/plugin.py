from core.plugin_system import DashboardPlugin
import time

class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.subscribers = []

        context.register_route("/api/plugins/live/events", self.stream)
        context.event_bus.subscribe("*", self.handle_event)

    def handle_event(self, data):
        for sub in list(self.subscribers):
            try:
                sub.append(data)
            except Exception:
                pass

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
                    handler.wfile.write(f"data: {event}\n\n".encode())
                    handler.wfile.flush()
                time.sleep(1)
        except Exception:
            pass
        finally:
            self.subscribers.remove(buffer)

        return {"_plugin_handled": True}
