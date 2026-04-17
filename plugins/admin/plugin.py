from lib.plugin_api import DashboardPlugin, PluginEvent
import json
import time
from .routes import register_routes


class Plugin(DashboardPlugin):

    def setup(self, context):
        super().setup(context)

        self.events = []

        # NEW: register health/alerts routes
        register_routes(context)

        # API
        context.register_route("/api/plugins/admin/status", self.get_status)
        context.register_route("/api/plugins/admin/plugins", self.get_plugins)
        context.register_route("/api/plugins/admin/events", self.get_events)
        context.register_route("/api/plugins/admin/stream", self.stream_events)

        # Subscribe to ALL events
        context.subscribe("*", self.capture_event)

        # UI
        context.register_dashboard_card(
            "admin_overview",
            "System Overview",
            render=self.render_card,
            order=0
        )

        self.set_healthy("Admin ready")

    def capture_event(self, event: PluginEvent):
        self.events.append({
            "type": event.type,
            "source": event.source,
            "severity": event.severity,
            "timestamp": event.timestamp
        })

        self.events = self.events[-100:]

    def get_status(self, handler=None):
        pm = self.context.get_service("plugin_manager")
        return {
            "plugins": pm.describe_plugins() if pm else [],
            "events": len(self.events)
        }

    def get_plugins(self, handler=None):
        pm = self.context.get_service("plugin_manager")
        return pm.describe_plugins() if pm else []

    def get_events(self, handler=None):
        return self.events

    def stream_events(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()

        try:
            last_index = 0
            while True:
                if last_index < len(self.events):
                    event = self.events[last_index]
                    payload = f"data: {json.dumps(event)}\n\n"
                    handler.wfile.write(payload.encode("utf-8"))
                    handler.wfile.flush()
                    last_index += 1
                else:
                    time.sleep(1)
        except Exception:
            return {"_plugin_handled": True}

    def render_card(self):
        return """
        <div>
            <h3>Plugins</h3>
            <ul id='plugin-list'></ul>

            <h3>Live Events</h3>
            <ul id='event-list'></ul>

            <script>
                async function loadPlugins() {
                    const res = await fetch('/api/plugins/admin/plugins');
                    const data = await res.json();
                    const el = document.getElementById('plugin-list');
                    el.innerHTML = '';
                    data.forEach(p => {
                        const status = p.health?.status || 'unknown';
                        const icon = status === 'healthy' ? '🟢' : status === 'degraded' ? '🟡' : status === 'failed' ? '🔴' : '⚪';
                        el.innerHTML += `<li>${icon} ${p.id}</li>`;
                    });
                }

                function startStream() {
                    const eventList = document.getElementById('event-list');
                    const evtSource = new EventSource('/api/plugins/admin/stream');

                    evtSource.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        const item = document.createElement('li');
                        item.textContent = `${data.type} (${data.severity})`;
                        eventList.prepend(item);

                        if (eventList.children.length > 10) {
                            eventList.removeChild(eventList.lastChild);
                        }
                    };
                }

                loadPlugins();
                startStream();
            </script>
        </div>
        """

    def stop(self):
        super().stop()
