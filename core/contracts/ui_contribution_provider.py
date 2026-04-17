from typing import Protocol, Any


class UiContributionProvider(Protocol):
    def register_ui(self, context: Any) -> None: ...
