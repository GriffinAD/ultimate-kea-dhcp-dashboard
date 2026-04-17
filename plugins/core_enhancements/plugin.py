from core.plugin_api import DashboardPlugin

class Plugin(DashboardPlugin):
    def setup(self, context):
        self.context = context
        context.subscribe("plugin.failure", self.on_failure)

    def on_failure(self, event):
        pm = self.context.get_service("plugin_manager")
        pid = event.payload.get("plugin") if hasattr(event, 'payload') else None
        if not pm or not pid:
            return
        p = pm.plugins.get(pid)
        if not p:
            return
        try:
            p.stop(); p.start()
        except Exception:
            pass
