
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any


class AuditLogger:
    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.log_path = self.root_dir / "core" / "registry" / "plugin_audit.log.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        plugin: str,
        permission: str | None,
        action: str,
        target: Any,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "plugin": plugin,
            "permission": permission,
            "action": action,
            "target": target,
            "status": status,
            "details": details or {},
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")

    def tail(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out
