from lib.plugin_system import DashboardPlugin

class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.events = []

        context.register_route("/api/plugins/admin/status", self.get_status)

        context.event_bus.subscribe("*", self.capture_event)

        context.register_dashboard_card(
            "plugin_admin",
            "Plugin Status",
            render=self.render_card,
            order=1
        )

    def capture_event(self, data):
        self.events.append(data)
        if len(self.events) > 20:
            self.events.pop(0)

    def get_status(self, handler=None):
        pm = self.context.get_service("plugin_manager")
        return {
            "plugins": pm.describe_plugins() if pm else [],
            "recent_events": self.events
        }

    def render_card(self):
        pm = self.context.get_service("plugin_manager")
        plugins = pm.describe_plugins() if pm else []

        html = "<ul>"
        for p in plugins:
            status = "✅" if p.get("enabled") else "❌"
            html += f"<li>{p['id']} {status}</li>"
        html += "</ul>"

        return html
