def get_health(context):
    return context.plugin_system.health.all()


def get_alerts(context):
    return context.plugin_system.alerts.list()


def list_plugins(context):
    pm = context.get_service("plugin_manager")
    if not pm:
        return []
    return pm.describe_plugins()
