from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
import threading
import uuid


@dataclass(slots=True)
class PluginEvent:
    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(slots=True)
class PluginHealth:
    status: str = "healthy"
    message: str = ""
    last_error: str | None = None
    last_success: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginManifest:
    id: str
    name: str
    version: str
    plugin_api_version: str
    entrypoint: str
    enabled_by_default: bool = True
    description: str = ""
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    optional_requires: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DashboardCard:
    id: str
    title: str
    order: int = 100
    render: Callable[[], str] | None = None


@dataclass(slots=True)
class RouteRegistration:
    path: str
    methods: list[str]
    handler: Callable[..., Any]


class EventBusProtocol(Protocol):
    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None: ...
    def emit(self, event: PluginEvent) -> None: ...


class SchedulerProtocol(Protocol):
    def every(self, name: str, interval_seconds: int, func: Callable[[], None]) -> None: ...
    def cancel(self, name: str) -> None: ...
    def cancel_all(self) -> None: ...


class PluginContextProtocol(Protocol):
    manifest: PluginManifest
    config: dict[str, Any]
    logger: Any
    event_bus: EventBusProtocol

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any]: ...
    def get_service(self, name: str, default: Any = None) -> Any: ...
    def register_service(self, name: str, service: Any) -> None: ...
    def register_route(self, path: str, handler: Callable[..., Any], methods: list[str] | None = None) -> None: ...
    def register_dashboard_card(self, card_id: str, title: str, render: Callable[[], str] | None = None, order: int = 100) -> None: ...
    def emit(self, event_type: str, payload: dict[str, Any] | None = None, severity: str = "info") -> None: ...


class DashboardPlugin(ABC):
    manifest: PluginManifest | None = None

    def __init__(self) -> None:
        self.context: PluginContextProtocol | None = None
        self._health = PluginHealth()
        self._started = False
        self._lock = threading.RLock()

    def setup(self, context: PluginContextProtocol) -> None:
        self.context = context

    def register(self, context: PluginContextProtocol) -> None:
        # Backward-compatible alias for older plugins.
        self.setup(context)

    def start(self) -> None:
        with self._lock:
            self._started = True

    def stop(self) -> None:
        with self._lock:
            self._started = False

    def health(self) -> PluginHealth:
        return self._health

    def set_healthy(self, message: str = "", **details: Any) -> None:
        self._health.status = "healthy"
        self._health.message = message
        self._health.last_error = None
        self._health.last_success = datetime.now(timezone.utc).isoformat()
        self._health.details.update(details)

    def set_degraded(self, message: str, **details: Any) -> None:
        self._health.status = "degraded"
        self._health.message = message
        self._health.details.update(details)

    def set_failed(self, message: str, error: Exception | str | None = None, **details: Any) -> None:
        self._health.status = "failed"
        self._health.message = message
        self._health.last_error = str(error) if error is not None else None
        self._health.details.update(details)
