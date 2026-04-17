import json
from pathlib import Path

class Marketplace:
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.registry_path = self.root / "core" / "plugin_registry.json"
        self.installed_path = self.root / "core" / "installed_plugins.json"

        self.registry = self._load(self.registry_path)
        self.installed = self._load(self.installed_path)

    def _load(self, path):
        try:
            return json.loads(path.read_text())
        except Exception:
            return []

    def _save(self, path, data):
        path.write_text(json.dumps(data, indent=2))

    def list_available(self):
        return self.registry

    def list_installed(self):
        return self.installed

    def install(self, plugin_id):
        if plugin_id not in self.installed:
            self.installed.append(plugin_id)
            self._save(self.installed_path, self.installed)
        return {"status": "installed"}

    def enable(self, plugin_id):
        return {"status": "enabled", "plugin": plugin_id}

    def disable(self, plugin_id):
        return {"status": "disabled", "plugin": plugin_id}
