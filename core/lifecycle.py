
from __future__ import annotations


VALID_LIFECYCLE_STATES = {
    "discovered",
    "validated",
    "blocked",
    "approved",
    "loaded",
    "running",
    "degraded",
    "failed",
    "quarantined",
    "disabled",
    "stopped",
}


class LifecycleRegistry:
    def __init__(self):
        self.states: dict[str, str] = {}

    def set(self, plugin_id: str, state: str) -> None:
        if state not in VALID_LIFECYCLE_STATES:
            raise ValueError(f"Invalid lifecycle state: {state}")
        self.states[plugin_id] = state

    def get(self, plugin_id: str) -> str:
        return self.states.get(plugin_id, "unknown")

    def snapshot(self) -> dict[str, str]:
        return dict(self.states)
