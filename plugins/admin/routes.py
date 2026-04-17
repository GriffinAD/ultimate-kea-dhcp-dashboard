def register_routes(context):
    from .services import get_health, get_alerts, list_plugins

    context.register_route(
        "/api/admin/health",
        lambda handler: get_health(context),
        methods=["GET"]
    )

    context.register_route(
        "/api/admin/alerts",
        lambda handler: get_alerts(context),
        methods=["GET"]
    )

    context.register_route(
        "/api/admin/plugins",
        lambda handler: list_plugins(context),
        methods=["GET"]
    )

    def restart_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        p = pm.plugins.get(pid) if pm else None
        if p:
            try:
                p.stop(); p.start()
                return {"status": "restarted"}
            except Exception as e:
                return {"error": str(e)}
        return {"error": "not found"}

    context.register_route(
        "/api/admin/plugins/restart",
        restart_plugin,
        methods=["POST"]
    )

    def get_ui_plugins(handler=None):
        pm = context.get_service("plugin_manager")
        if not pm:
            return []

        known = {
            "admin": {"route": "/admin", "title": "Admin"},
            "automation_engine": {"route": "/automation", "title": "Automation"}
        }

        return [
            {
                "plugin": pid,
                "route": known[pid]["route"],
                "title": known[pid]["title"]
            }
            for pid in pm.plugins.keys()
            if pid in known
        ]

    context.register_route(
        "/api/ui/plugins",
        get_ui_plugins,
        methods=["GET"]
    )
