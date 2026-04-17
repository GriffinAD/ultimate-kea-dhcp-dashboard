from typing import Protocol, Any


class KeaStatusProvider(Protocol):
    def get_status(self) -> dict[str, Any]: ...
