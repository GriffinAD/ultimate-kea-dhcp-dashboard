from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from lib.event_bus import EventBus
from lib.scheduler import Scheduler
from lib.plugin_api import PluginEvent, DashboardPlugin


# Re-export for backward compatibility
DashboardPlugin = DashboardPlugin


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
    def __init__(self, *, root_dir: Path, config: dict, event_bus: EventBus) -> None:
        self.root_dir = Path(root_dir)
        self._root_config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger("ukd.plugins")
        self.services: Dict[str, Any] = {}
        self.routes: List[RouteRegistration] = []
        self.cards: List[DashboardCard] = []

    @property
    def config(self) -> dict:
        return self._root_config

    def get_plugin_config(self, plugin_id: str) -> dict:
        return self._root_config.get("plugins", {}).get(plugin_id, {})

    def register_service(self, name: str, service: Any) -> None:
        self.services[name] = service

    def get_service(self, name: str, default: Any = None) -> Any:
        return self.services.get(name, default)

    def register_route(self, path: str, handler: Callable[..., Any], methods=None) -> None:
        self.routes.append(RouteRegistration(path=path, methods=list(methods or ["GET"]), handler=handler))

    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
        self.cards.append(DashboardCard(id=card_id, title=title, render=render, order=order))

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
        self.event_bus.subscribe(event_type, handler)

    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        self.event_bus.emit(PluginEvent(type=event_type, source="system", payload=payload or {}, severity=severity))


class PluginManager:
    def __init__(self, *, root_dir: Path, config: dict, plugins_dir: str = "plugins") -> None:
        self.root_dir = Path(root_dir)
        self.plugins_dir = self.root_dir / plugins_dir
        self.config = config
        self.event_bus = EventBus(logging.getLogger("ukd.events"))
        self.scheduler = Scheduler(logging.getLogger("ukd.scheduler"))
        self.context = PluginContext(root_dir=self.root_dir, config=config, event_bus=self.event_bus)
        self.context.register_service("scheduler", self.scheduler)
        self.manifests: Dict[str, PluginManifest] = {}
        self.plugins: Dict[str, Any] = {}
        self.logger = logging.getLogger("ukd.plugins")

    def discover(self) -> Dict[str, PluginManifest]:
        manifests = {}
        for manifest_path in self.plugins_dir.glob("*/manifest.json"):
            try:
                data = json.loads(manifest_path.read_text())
                manifest = PluginManifest.from_dict(data)
                manifests[manifest.id] = manifest
            except Exception:
                self.logger.exception("Failed to parse %s", manifest_path)
        self.manifests = manifests
        return manifests

    def _load_module(self, manifest: PluginManifest):
        module_path, _, class_name = manifest.entrypoint.partition(":")
        file_path = self.plugins_dir / manifest.id / f"{module_path}.py"
        spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, class_name)

    def load_enabled_plugins(self):
        for pid, manifest in self.manifests.items():
            try:
                cls = self._load_module(manifest)
                plugin = cls()
                plugin.manifest = manifest

                if hasattr(plugin, "setup"):
                    plugin.setup(self.context)
                else:
                    plugin.register(self.context)

                self.plugins[pid] = plugin
                self.context.register_service(pid, plugin)
                self.logger.info("Loaded %s", pid)
            except Exception:
                self.logger.exception("Failed plugin %s", pid)

    def start_all(self):
        for pid, plugin in self.plugins.items():
            try:
                plugin.start()
            except Exception:
                self.logger.exception("Start failed %s", pid)

    def stop_all(self):
        self.scheduler.cancel_all()
        for pid, plugin in reversed(list(self.plugins.items())):
            try:
                plugin.stop()
            except Exception:
                self.logger.exception("Stop failed %s", pid)

    def get_registered_routes(self):
        return list(self.context.routes)

    def get_dashboard_cards(self):
        return sorted(self.context.cards, key=lambda c: c.order)
