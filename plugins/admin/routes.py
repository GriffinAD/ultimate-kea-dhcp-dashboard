def register_routes(context):
    from .services import (
        get_health,
        get_alerts,
        list_plugins,
        list_marketplace_plugins,
        install_marketplace_plugin,
    )

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
        admin_manifest = pm.manifests.get("admin") if pm else None
        context.security.require("admin", admin_manifest, "plugin_control")
        if pm:
            pm.restart_plugin(pid)
            return {"status": "restarted"}
        return {"error": "not found"}

    context.register_route(
        "/api/admin/plugins/restart",
        restart_plugin,
        methods=["POST"]
    )

    def enable_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        admin_manifest = pm.manifests.get("admin") if pm else None
        context.security.require("admin", admin_manifest, "plugin_control")
        if pm:
            pm.enable_plugin(pid)
            return {"status": "enabled"}
        return {"error": "not found"}

    context.register_route(
        "/api/admin/plugins/enable",
        enable_plugin,
        methods=["POST"]
    )

    def disable_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        admin_manifest = pm.manifests.get("admin") if pm else None
        context.security.require("admin", admin_manifest, "plugin_control")
        if pm:
            pm.disable_plugin(pid)
            return {"status": "disabled"}
        return {"error": "not found"}

    context.register_route(
        "/api/admin/plugins/disable",
        disable_plugin,
        methods=["POST"]
    )

    context.register_route(
        "/api/marketplace/plugins",
        lambda handler: list_marketplace_plugins(context),
        methods=["GET"]
    )

    def install_marketplace(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")
        pm = context.get_service("plugin_manager")
        admin_manifest = pm.manifests.get("admin") if pm else None
        context.security.require("admin", admin_manifest, "marketplace_install")
        return install_marketplace_plugin(context, pid)

    context.register_route(
        "/api/marketplace/install",
        install_marketplace,
        methods=["POST"]
    )

    def get_ui_plugins(handler=None):
        pm = context.get_service("plugin_manager")
        if not pm:
            return []

        known = {
            "admin": {"route": "/admin", "title": "Admin"},
            "automation_engine": {"route": "/automation", "title": "Automation"},
            "kea_ha": {"route": "/kea", "title": "Kea HA"},
            "home_assistant": {"route": "/home-assistant", "title": "Home Assistant"},
            "prometheus": {"route": "/prometheus", "title": "Prometheus"}
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
