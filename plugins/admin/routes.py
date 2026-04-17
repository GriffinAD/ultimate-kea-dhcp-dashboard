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
