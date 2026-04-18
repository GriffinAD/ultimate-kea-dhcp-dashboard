import json
from pathlib import Path


from core.policy import PolicyEngine

class SecurityManager:
    TRUST_LEVELS = {"local", "trusted", "core"}

    PERMISSION_RULES = {
        "network.outbound": {"trusted", "core"},
        "network.inbound": {"core"},
        "network.scan": {"trusted", "core"},
        "plugin.control": {"trusted", "core"},
        "plugin.install": {"core"},
        "plugin.disable": {"trusted", "core"},
        "plugin.reload": {"trusted", "core"},
        "system.exec": {"trusted", "core"},
        "system.files.read": {"trusted", "core"},
        "system.files.write": {"trusted", "core"},
        "system.destructive": {"core"},
        "kea.read": {"local", "trusted", "core"},
        "kea.write": {"trusted", "core"},
        "kea.ha.control": {"trusted", "core"},
        "integration.home_assistant": {"trusted", "core"},
        "integration.webhook": {"trusted", "core"},
        "integration.prometheus": {"trusted", "core"},
        "integration.mobile_push": {"trusted", "core"},
        "secret.read": {"trusted", "core"},
        "secret.write": {"core"},
    }

    def __init__(self, root_dir, config=None):
        self.root_dir = Path(root_dir)
        self.config = config or {}
        self.policy = PolicyEngine(self.config)
        self.trusted_plugins_path = self.root_dir / "core" / "registry" / "trusted_plugins.json"
        self.trusted_plugins = self._load_trusted_plugins()

    def _load_trusted_plugins(self):
        try:
            data = json.loads(self.trusted_plugins_path.read_text())
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 set(data)
        except Exception:
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 set()

    def _manifest_value(self, manifest, name, default=None):
        if manifest is None:
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 default
        if isinstance(manifest, dict):
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 manifest.get(name, default)
        
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 getattr(manifest, name, default)

    def get_trust_level(self, plugin_id, manifest):
        if plugin_id in self.trusted_plugins:
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 "trusted"

        publisher = self._manifest_value(manifest, "publisher")
        if publisher == "core":
            
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 "core"

        declared = self._manifest_value(manifest, "trust_level", "local")
        
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 declared if declared in self.TRUST_LEVELS else "local"

    def get_permissions(self, manifest):
        permissions = self._manifest_value(manifest, "permissions", []) or []
        
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 set(permissions)

    def validate_permissions(self, plugin_id, manifest):
        trust = self.get_trust_level(plugin_id, manifest)
        permissions = self.get_permissions(manifest)

        errors = []
        for permission in permissions:
            allowed_trusts = self.PERMISSION_RULES.get(permission)
            if allowed_trusts is None:
                errors.append(f"Unknown permission: {permission}")
                continue
            if trust not in allowed_trusts:
                errors.append(
                    f"{plugin_id} trust level {trust} insufficient for {permission}"
                )
        
        # policy enforcement
        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for {permission}")

        return
 errors

    def require(self, plugin_id, manifest, permission):
        permissions = self.get_permissions(manifest)
        if permission not in permissions:
            raise PermissionError(f"{plugin_id} missing permission: {permission}")

        trust = self.get_trust_level(plugin_id, manifest)
        allowed_trusts = self.PERMISSION_RULES.get(permission)
        if allowed_trusts is None:
            raise PermissionError(f"{plugin_id} requested unknown permission: {permission}")

        if trust not in allowed_trusts:
            raise PermissionError(
                f"{plugin_id} trust level {trust} insufficient for {permission}"
            )

        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for permission: {permission}")
