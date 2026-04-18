
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


class QuarantineRegistry:
    def __init__(self, root_dir: Path):
        self.path = Path(root_dir) / "core" / "registry" / "plugin_quarantine.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_all(self) -> dict:
        return self._load()

    def is_quarantined(self, plugin_id: str) -> bool:
        return plugin_id in self._load()

    def quarantine(self, plugin_id: str, reason: str) -> None:
        data = self._load()
        data[plugin_id] = {
            "reason": reason,
            "quarantined_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def release(self, plugin_id: str) -> None:
        data = self._load()
        data.pop(plugin_id, None)
        self._save(data)
