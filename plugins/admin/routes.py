def register_routes(context):
    from .services import get_health, get_alerts

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
