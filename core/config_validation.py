
from __future__ import annotations

from pathlib import Path
import json

try:
    import jsonschema
except Exception:
    jsonschema = None


def validate_config(root_dir: Path, plugin_id: str, manifest, config: dict) -> list[str]:
    if not manifest.config_schema:
        return []

    if jsonschema is None:
        return ["jsonschema dependency not installed"]

    schema_path = Path(root_dir) / "plugins" / plugin_id / manifest.config_schema
    if not schema_path.exists():
        return [f"config schema not found: {schema_path}"]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(config or {}, schema)
        return []
    except Exception as exc:
        return [str(exc)]
