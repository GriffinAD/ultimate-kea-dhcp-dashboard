PLUGIN_API_VERSION = "1.0"


def _major(version: str) -> str:
    return version.split(".", 1)[0]


def validate_manifest(manifest) -> list[str]:
    errors = []

    if not manifest.id:
        errors.append("Missing plugin id")

    if not manifest.entrypoint:
        errors.append("Missing entrypoint")

    if not manifest.plugin_api_version:
        errors.append("Missing plugin_api_version")
    elif _major(manifest.plugin_api_version) != _major(PLUGIN_API_VERSION):
        errors.append(
            f"Incompatible plugin_api_version: {manifest.plugin_api_version} "
            f"(runtime supports {PLUGIN_API_VERSION})"
        )

    if manifest.trust_level not in {"local", "trusted", "core"}:
        errors.append(f"Invalid trust_level: {manifest.trust_level}")

    for permission in manifest.permissions:
        if "." not in permission:
            errors.append(f"Invalid permission name: {permission}")

    for route in manifest.contributes.routes:
        valid_prefixes = [f"/api/plugins/{manifest.id}/"]
        if manifest.trust_level == "core":
            valid_prefixes.append("/api/")
        if not any(route.path.startswith(prefix) for prefix in valid_prefixes):
            errors.append(f"Invalid route path: {route.path}")
        if not route.methods:
            errors.append(f"Route missing methods: {route.path}")

    for provided in manifest.provides:
        if "." not in provided and provided not in {"scheduler", "plugin_manager", "event_bus"}:
            errors.append(f"Invalid provided service name: {provided}")

    for required in manifest.requires_services:
        if "." not in required and required not in {"scheduler", "plugin_manager", "event_bus"}:
            errors.append(f"Invalid required service name: {required}")

    if manifest.id == "admin":
        if manifest.publisher != "core" or manifest.trust_level != "core":
            errors.append("admin plugin must be publisher=core and trust_level=core")

    return errors


def validation_warnings(manifest) -> list[str]:
    warnings = []
    sensitive = {"network.outbound", "system.exec", "integration.home_assistant"}
    if sensitive.intersection(set(manifest.permissions)) and not manifest.config_schema:
        warnings.append(f"{manifest.id} has sensitive permissions but no config_schema")
    return warnings
