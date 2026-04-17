from __future__ import annotations

from collections import defaultdict
from typing import Callable
from lib.plugin_api import PluginEvent


class EventBus:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._subscribers: dict[str, list[tuple[str | None, Callable[[PluginEvent], None]]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None], owner: str | None = None) -> None:
        self._subscribers[event_type].append((owner, handler))

    def unsubscribe_owner(self, owner: str) -> None:
        for event_type, handlers in list(self._subscribers.items()):
            self._subscribers[event_type] = [entry for entry in handlers if entry[0] != owner]

    def emit(self, event: PluginEvent) -> None:
        handlers = list(self._subscribers.get(event.type, []))

        namespace = event.type.rsplit(".", 1)[0] + ".*" if "." in event.type else None
        if namespace:
            handlers.extend(self._subscribers.get(namespace, []))

        handlers.extend(self._subscribers.get("*", []))

        for _owner, handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                self._logger.exception(
                    "Event handler failed for event %s from %s: %s",
                    event.type,
                    event.source,
                    exc,
                )

    def publish(self, event_name: str, payload: dict | None = None) -> None:
        self.emit(PluginEvent(type=event_name, source="legacy", payload=payload or {}))
