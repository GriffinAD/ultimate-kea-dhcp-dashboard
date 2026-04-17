from core.marketplace import Marketplace


def get_health(context):
    return context.plugin_system.health.all()


def get_alerts(context):
    return context.plugin_system.alerts.list()


def list_plugins(context):
    pm = context.get_service("plugin_manager")
    if not pm:
        return []
    return pm.describe_plugins()


def list_marketplace_plugins(context):
    marketplace = Marketplace(context.root_dir)
    installed = set(marketplace.list_installed())
    return [
        {
            **plugin,
            "installed": plugin["id"] in installed
        }
        for plugin in marketplace.list_available()
    ]


def install_marketplace_plugin(context, plugin_id):
    marketplace = Marketplace(context.root_dir)
    return marketplace.install(plugin_id)
