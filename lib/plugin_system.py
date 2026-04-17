"""Plugin system core for Ultimate Kea Dashboard.

This module provides a lightweight plugin framework designed to fit the
current architecture of the dashboard, which uses a custom HTTP server and a
single Python entrypoint rather than Flask or FastAPI.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


class EventBus:
    """Simple in-process pub/sub event bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_name: str, handler: Callable[[dict], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event_name, []).append(handler)

    def publish(self, event_name: str, payload: Optional[dict] = None) -> None:
        payload = payload or {}
        with self._lock:
            handlers = list(self._subscribers.get(event_name, []))
            wildcard_handlers = list(self._subscribers.get("*", []))

        for handler in handlers + wildcard_handlers:
            try:
                handler(payload)
            except Exception:
                logging.getLogger("ukd.plugins").exception(
                    "Plugin event handler failed for %s", event_name
                )


@dataclass
class DashboardCard:
    id: str
    title: str
    order: int = 100
    render: Optional[Callable[[], str]] = None


@dataclass
class RouteRegistration:
    path: str
    methods: Iterable[str]
    handler: Callable[..., Any]


@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    entrypoint: str
    enabled_by_default: bool = True
    depends_on: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            version=data.get("version", "0.1.0"),
            entrypoint=data["entrypoint"],
            enabled_by_default=data.get("enabled_by_default", True),
            depends_on=list(data.get("depends_on", [])),
            provides=list(data.get("provides", [])),
            description=data.get("description", ""),
        )


class PluginContext:
    """Context shared with plugins at registration time."""

    def __init__(self, *, root_dir: Path, config: dict, event_bus: EventBus) -> None:
        self.root_dir = Path(root_dir)
        self.config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger("ukd.plugins")
        self.services: Dict[str, Any] = {}
        self.routes: List[RouteRegistration] = []
        self.cards: List[DashboardCard] = []

    def register_service(self, name: str, service: Any) -> None:
        self.services[name] = service

    def get_service(self, name: str, default: Any = None) -> Any:
        return self.services.get(name, default)

    def register_route(
        self,
        path: str,
        handler: Callable[..., Any],
        methods: Optional[Iterable[str]] = None,
    ) -> None:
        self.routes.append(
            RouteRegistration(path=path, methods=list(methods or ["GET"]), handler=handler)
        )

    def register_dashboard_card(
        self,
        card_id: str,
        title: str,
        render: Optional[Callable[[], str]] = None,
        order: int = 100,
    ) -> None:
        self.cards.append(DashboardCard(id=card_id, title=title, render=render, order=order))


class DashboardPlugin:
    """Base class for dashboard plugins."""

    manifest: Optional[PluginManifest] = None

    def register(self, context: PluginContext) -> None:
        """Called once after the plugin is loaded."""

    def start(self) -> None:
        """Called after all plugins have been registered."""

    def stop(self) -> None:
        """Called when the application is shutting down."""


class PluginManager:
    """Discovers, loads, and manages plugins."""

    def __init__(
        self,
        *,
        root_dir: Path,
        config: dict,
        plugins_dir: str = "plugins",
        enabled_plugins: Optional[Iterable[str]] = None,
    ) -> None:
        self.root_dir = Path(root_dir)
        self.plugins_dir = self.root_dir / plugins_dir
        self.config = config
        self.enabled_plugins = set(enabled_plugins or [])
        self.event_bus = EventBus()
        self.context = PluginContext(
            root_dir=self.root_dir,
            config=self.config,
            event_bus=self.event_bus,
        )
        self.manifests: Dict[str, PluginManifest] = {}
        self.plugins: Dict[str, DashboardPlugin] = {}
        self.logger = logging.getLogger("ukd.plugins")

    def discover(self) -> Dict[str, PluginManifest]:
        manifests: Dict[str, PluginManifest] = {}
        if not self.plugins_dir.exists():
            self.logger.info("No plugins directory found at %s", self.plugins_dir)
            self.manifests = manifests
            return manifests

        for manifest_path in sorted(self.plugins_dir.glob("*/manifest.json")):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = PluginManifest.from_dict(data)
                manifests[manifest.id] = manifest
            except Exception:
                self.logger.exception("Failed to parse plugin manifest %s", manifest_path)

        self.manifests = manifests
        return manifests

    def _is_enabled(self, manifest: PluginManifest) -> bool:
        if self.enabled_plugins:
            return manifest.id in self.enabled_plugins
        return manifest.enabled_by_default

    def _load_module(self, manifest: PluginManifest):
        module_path, _, class_name = manifest.entrypoint.partition(":")
        file_path = self.plugins_dir / manifest.id / f"{module_path}.py"
        if not file_path.exists():
            raise FileNotFoundError(f"Plugin entrypoint file not found: {file_path}")

        spec = importlib.util.spec_from_file_location(
            f"ukd_plugin_{manifest.id}", file_path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, class_name

    def load_enabled_plugins(self) -> Dict[str, DashboardPlugin]:
        if not self.manifests:
            self.discover()

        for plugin_id, manifest in self.manifests.items():
            if not self._is_enabled(manifest):
                continue
            try:
                module, class_name = self._load_module(manifest)
                plugin_class = getattr(module, class_name)
                plugin = plugin_class()
                plugin.manifest = manifest
                plugin.register(self.context)
                self.plugins[plugin_id] = plugin
                self.context.register_service(plugin_id, plugin)
                self.logger.info("Loaded plugin %s v%s", manifest.id, manifest.version)
            except Exception:
                self.logger.exception("Failed to load plugin %s", plugin_id)

        return self.plugins

    def start_all(self) -> None:
        for plugin_id, plugin in self.plugins.items():
            try:
                plugin.start()
                self.logger.info("Started plugin %s", plugin_id)
            except Exception:
                self.logger.exception("Failed to start plugin %s", plugin_id)

    def stop_all(self) -> None:
        for plugin_id, plugin in reversed(list(self.plugins.items())):
            try:
                plugin.stop()
                self.logger.info("Stopped plugin %s", plugin_id)
            except Exception:
                self.logger.exception("Failed to stop plugin %s", plugin_id)

    def get_registered_routes(self) -> List[RouteRegistration]:
        return list(self.context.routes)

    def get_dashboard_cards(self) -> List[DashboardCard]:
        return sorted(self.context.cards, key=lambda card: card.order)

    def describe_plugins(self) -> List[dict]:
        descriptions = []
        for manifest in self.manifests.values():
            descriptions.append(
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "enabled": manifest.id in self.plugins,
                    "description": manifest.description,
                    "provides": manifest.provides,
                }
            )
        return descriptions
