from typing import Protocol


class MetricsProvider(Protocol):
    def render_metrics(self) -> str: ...
