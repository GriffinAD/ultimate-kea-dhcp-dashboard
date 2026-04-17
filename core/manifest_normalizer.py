LEGACY_CAPABILITY_MAP = {
    "network_outbound": "network.outbound",
    "plugin_control": "plugin.control",
    "marketplace_install": "plugin.install",
    "destructive": "system.destructive",
}


def normalize_manifest(data: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    normalized = dict(data)

    if "plugin_api_version" not in normalized:
        normalized["plugin_api_version"] = "1.0"
        warnings.append("Manifest missing plugin_api_version; defaulted to 1.0")

    if "permissions" not in normalized:
        permissions = []
        capabilities = normalized.get("capabilities", {}) or {}
        for key, value in capabilities.items():
            if value and key in LEGACY_CAPABILITY_MAP:
                permissions.append(LEGACY_CAPABILITY_MAP[key])
        normalized["permissions"] = permissions
        if capabilities:
            warnings.append("Legacy capabilities converted to permissions; update manifest to v1")

    normalized.setdefault("contributes", {})
    normalized.setdefault("requires_services", [])
    normalized.setdefault("depends_on", [])
    normalized.setdefault("provides", [])

    return normalized, warnings
