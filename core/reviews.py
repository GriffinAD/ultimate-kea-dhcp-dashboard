
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


class ReviewRegistry:
    def __init__(self, root_dir: Path):
        self.path = Path(root_dir) / "core" / "registry" / "plugin_reviews.json"
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

    def get(self, plugin_id: str) -> dict:
        return self._load().get(plugin_id, {"review_state": "unapproved"})

    def set(self, plugin_id: str, review_state: str, approved_by: str, notes: str = "") -> None:
        data = self._load()
        data[plugin_id] = {
            "review_state": review_state,
            "approved_by": approved_by,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        }
        self._save(data)
