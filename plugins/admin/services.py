def get_health(context):
    return context.plugin_system.health.all()


def get_alerts(context):
    return context.plugin_system.alerts.list()
