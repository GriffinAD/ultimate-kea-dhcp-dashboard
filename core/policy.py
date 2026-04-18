
from __future__ import annotations

import fnmatch


class PolicyEngine:
    def __init__(self, config: dict):
        self.config = config.get("plugin_policy", {})

    def get_runtime_mode(self) -> str:
        return self.config.get("runtime_mode", "production")

    def is_permission_allowed(self, plugin_id: str, permission: str) -> bool:
        if permission in self.config.get("deny_permissions", []):
            return False

        overrides = self.config.get("plugin_overrides", {}).get(plugin_id, {})
        allowed = overrides.get("allow_permissions")
        if allowed is not None:
            return permission in allowed

        denied = overrides.get("deny_permissions", [])
        if permission in denied:
            return False

        return True

    def is_host_allowed(self, plugin_id: str, host: str) -> bool:
        overrides = self.config.get("plugin_overrides", {}).get(plugin_id, {})
        patterns = overrides.get("allow_hosts", [])
        if not patterns:
            return True
        return any(fnmatch.fnmatch(host, pattern) for pattern in patterns)

    def is_command_allowed(self, plugin_id: str, command: str) -> bool:
        overrides = self.config.get("plugin_overrides", {}).get(plugin_id, {})
        allowed = overrides.get("allowed_commands", [])
        if not allowed:
            return False
        return command in allowed

    def is_review_state_allowed(self, review_state: str) -> bool:
        mode = self.get_runtime_mode()
        if mode == "dev":
            return True
        if mode == "lab":
            return review_state in {"core", "reviewed", "local"}
        return review_state in {"core", "reviewed"}

    def requires_explicit_approval(self, permissions: list[str], consumes_events: list[str]) -> bool:
        sensitive = {
            "network.outbound",
            "system.exec",
            "plugin.control",
            "plugin.install",
            "kea.write",
            "kea.ha.control",
        }
        return bool(sensitive.intersection(set(permissions))) or "*" in set(consumes_events)
