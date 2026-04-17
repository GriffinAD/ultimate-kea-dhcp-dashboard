import json
from pathlib import Path


class SecurityManager:
    def __init__(self, root_dir, config=None):
        self.root_dir = Path(root_dir)
        self.config = config or {}
        self.trusted_plugins_path = self.root_dir / "core" / "registry" / "trusted_plugins.json"
        self.trusted_plugins = self._load_trusted_plugins()

    def _load_trusted_plugins(self):
        try:
            data = json.loads(self.trusted_plugins_path.read_text())
            return set(data)
        except Exception:
            return set()

    def _manifest_value(self, manifest, name, default=None):
        if manifest is None:
            return default
        if isinstance(manifest, dict):
            return manifest.get(name, default)
        return getattr(manifest, name, default)

    def get_trust_level(self, plugin_id, manifest):
        if plugin_id in self.trusted_plugins:
            return "trusted"
        publisher = self._manifest_value(manifest, "publisher")
        if publisher == "core":
            return "core"
        declared = self._manifest_value(manifest, "trust_level")
        if declared:
            return declared
        return "local"

    def get_capabilities(self, manifest):
        caps = self._manifest_value(manifest, "capabilities", {})
        return caps or {}

    def require(self, plugin_id, manifest, capability):
        caps = self.get_capabilities(manifest)
        if not caps.get(capability, False):
            raise PermissionError(f"{plugin_id} missing capability: {capability}")

        trust = self.get_trust_level(plugin_id, manifest)
        if capability in ["network_outbound", "plugin_control"] and trust not in ["trusted", "core"]:
            raise PermissionError(f"{plugin_id} trust level {trust} insufficient for {capability}")
        if capability in ["marketplace_install", "destructive"] and trust != "core":
            raise PermissionError(f"{plugin_id} trust level {trust} insufficient for {capability}")
