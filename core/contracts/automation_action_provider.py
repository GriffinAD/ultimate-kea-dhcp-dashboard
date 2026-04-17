from typing import Protocol, Any


class AutomationActionProvider(Protocol):
    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]: ...
