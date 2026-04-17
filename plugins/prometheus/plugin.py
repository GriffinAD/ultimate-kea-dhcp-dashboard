from lib.plugin_system import DashboardPlugin

class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        context.register_route("/metrics", self.metrics)

    def metrics(self, handler=None):
        try:
            kea = self.context.get_service("kea_ha")
        except Exception:
            kea = None

        # basic fallback: call API route directly if no service yet
        status = {}
        try:
            from plugins.kea_ha.plugin import Plugin as KeaPlugin
            kea_plugin = KeaPlugin()
            kea_plugin.context = self.context
            status = kea_plugin.get_status()
        except Exception:
            pass

        lines = []

        active = status.get("active_node")
        if active:
            lines.append(f"kea_active_node{{node=\"{active}\"}} 1")

        for node, data in status.get("nodes", {}).items():
            reachable = 1 if data.get("reachable") else 0
            lines.append(f"kea_node_reachable{{node=\"{node}\"}} {reachable}")

            state = data.get("local_state") or "unknown"
            lines.append(f"kea_node_state{{node=\"{node}\",state=\"{state}\"}} 1")

        return "\n".join(lines)

    def start(self):
        pass

    def stop(self):
        pass
