from typing import Protocol, Any


class AlertProvider(Protocol):
    def send_alert(self, level: str, message: str, payload: dict[str, Any] | None = None) -> None: ...
