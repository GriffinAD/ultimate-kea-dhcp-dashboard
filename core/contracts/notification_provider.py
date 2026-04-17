from typing import Protocol, Any


class NotificationProvider(Protocol):
    def notify(self, event_name: str, payload: dict[str, Any]) -> dict[str, Any]: ...
