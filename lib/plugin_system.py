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
from core.security import SecurityManager


DashboardPlugin = DashboardPlugin


@dataclass
class DashboardCard:
    id: str
    title: str
    order: int = 100
    render: Optional[Callable[[], str]] = None
    plugin_id: Optional[str] = None


@dataclass
class RouteRegistration:
    path: str
    methods: Iterable[str]
    handler: Callable[..., Any]
    plugin_id: Optional[str] = None


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
    publisher: str = "local"
    trust_level: str = "local"
    capabilities: Dict[str, bool] = field(default_factory=dict)

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
            publisher=data.get("publisher", "local"),
            trust_level=data.get("trust_level", "local"),
            capabilities=data.get("capabilities", {}),
        )


class PluginContext:
    def __init__(self, *, root_dir: Path, config: dict, event_bus: EventBus) -> None:
        self.root_dir = Path(root_dir)
        self._root_config = config
        self.event_bus = event_bus
        self.logger = logging.getLogger("ukd.plugins")
        self.services: Dict[str, Any] = {}
        self.service_owners: Dict[str, str] = {}
        self.routes: List[RouteRegistration] = []
        self.cards: List[DashboardCard] = []
        self._current_plugin: Optional[str] = None
        self.security = SecurityManager(self.root_dir, config)

    @property
    def config(self) -> dict:
        return self._root_config

    def set_current_plugin(self, plugin_id: Optional[str]) -> None:
        self._current_plugin = plugin_id

    def require_capability(self, capability: str):
        pid = self._current_plugin
        plugin = self.services.get(pid)
        manifest = getattr(plugin, "manifest", None)
        self.security.require(pid, manifest, capability)

    def get_plugin_config(self, plugin_id: str) -> dict:
        return self._root_config.get("plugins", {}).get(plugin_id, {})

    def register_service(self, name: str, service: Any) -> None:
        self.services[name] = service
        if self._current_plugin:
            self.service_owners[name] = self._current_plugin

    def get_service(self, name: str, default: Any = None) -> Any:
        return self.services.get(name, default)

    def unregister_services_by_owner(self, plugin_id: str) -> None:
        owned = [name for name, owner in self.service_owners.items() if owner == plugin_id]
        for name in owned:
            self.services.pop(name, None)
            self.service_owners.pop(name, None)

    def register_route(self, path: str, handler: Callable[..., Any], methods=None) -> None:
        self.routes.append(RouteRegistration(path=path, methods=list(methods or ["GET"]), handler=handler, plugin_id=self._current_plugin))

    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
        self.cards.append(DashboardCard(id=card_id, title=title, render=render, order=order, plugin_id=self._current_plugin))

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
        self.event_bus.subscribe(event_type, handler, owner=self._current_plugin)

    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        self.event_bus.emit(PluginEvent(type=event_type, source=self._current_plugin or "system", payload=payload or {}, severity=severity))


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
        self.blocked: Dict[str, str] = {}
        self.logger = logging.getLogger("ukd.plugins")
        self.state_file = self.plugins_dir / ".state.json"
        self.plugin_state = self._load_state()

    def _load_state(self) -> Dict[str, bool]:
        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return {}

    def _save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.plugin_state, indent=2))

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

    def _is_allowed(self, pid: str, manifest: PluginManifest):
        trust = self.context.security.get_trust_level(pid, manifest)
        caps = manifest.capabilities or {}

        if trust == "local" and caps.get("network_outbound"):
            return False, "untrusted plugin with outbound network"
        if trust != "core" and caps.get("marketplace_install"):
            return False, "only core plugins can install plugins"
        if trust not in ["trusted", "core"] and caps.get("plugin_control"):
            return False, "insufficient trust for plugin control"
        if trust != "core" and caps.get("destructive"):
            return False, "destructive capability requires core trust"

        return True, None

    def _load_module(self, manifest: PluginManifest):
        module_path, _, class_name = manifest.entrypoint.partition(":")
        file_path = self.plugins_dir / manifest.id / f"{module_path}.py"
        spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, class_name)

    def _load_single_plugin(self, pid: str, manifest: PluginManifest) -> bool:
        if pid in self.plugins:
            return True

        allowed, reason = self._is_allowed(pid, manifest)
        if not allowed:
            self.blocked[pid] = reason
            self.logger.warning("Blocked plugin %s: %s", pid, reason)
            return False

        try:
            cls = self._load_module(manifest)
            plugin = cls()
            plugin.manifest = manifest

            self.context.set_current_plugin(pid)
            if hasattr(plugin, "setup"):
                plugin.setup(self.context)
            else:
                plugin.register(self.context)
            self.context.set_current_plugin(None)

            self.plugins[pid] = plugin
            self.context.register_service(pid, plugin)
            try:
                plugin.start()
            except Exception:
                self.logger.exception("Start failed %s", pid)
            self.blocked.pop(pid, None)
            self.logger.info("Loaded %s", pid)
            return True
        except Exception:
            self.context.set_current_plugin(None)
            self.logger.exception("Failed plugin %s", pid)
            return False

    def load_enabled_plugins(self):
        for pid, manifest in self.manifests.items():
            enabled = self.plugin_state.get(pid, manifest.enabled_by_default)
            if enabled:
                self._load_single_plugin(pid, manifest)

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

    def unload_plugin(self, plugin_id: str) -> bool:
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return False

        try:
            plugin.stop()
        except Exception:
            self.logger.exception("Stop failed %s", plugin_id)

        self.context.routes = [r for r in self.context.routes if r.plugin_id != plugin_id]
        self.context.cards = [c for c in self.context.cards if c.plugin_id != plugin_id]
        self.context.unregister_services_by_owner(plugin_id)
        self.event_bus.unsubscribe_owner(plugin_id)
        self.plugins.pop(plugin_id, None)
        return True

    def enable_plugin(self, plugin_id: str) -> bool:
        manifest = self.manifests.get(plugin_id)
        if not manifest:
            return False
        self.plugin_state[plugin_id] = True
        self._save_state()
        return self._load_single_plugin(plugin_id, manifest)

    def disable_plugin(self, plugin_id: str) -> bool:
        self.plugin_state[plugin_id] = False
        self._save_state()
        return self.unload_plugin(plugin_id)

    def restart_plugin(self, plugin_id: str) -> bool:
        was_enabled = self.plugin_state.get(plugin_id, True)
        self.unload_plugin(plugin_id)
        if was_enabled:
            return self.enable_plugin(plugin_id)
        return True

    def get_registered_routes(self):
        return list(self.context.routes)

    def get_dashboard_cards(self):
        return sorted(self.context.cards, key=lambda c: c.order)

    def describe_plugins(self):
        descriptions = []
        for manifest in self.manifests.values():
            plugin = self.plugins.get(manifest.id)
            health = None
            if plugin and hasattr(plugin, "health"):
                try:
                    h = plugin.health()
                    health = {
                        "status": h.status,
                        "message": h.message,
                        "last_error": h.last_error,
                        "last_success": h.last_success,
                        "details": h.details,
                    }
                except Exception:
                    health = {"status": "failed", "message": "health() failed"}

            descriptions.append({
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "enabled": self.plugin_state.get(manifest.id, manifest.enabled_by_default) and manifest.id in self.plugins,
                "configured_enabled": self.plugin_state.get(manifest.id, manifest.enabled_by_default),
                "description": manifest.description,
                "provides": manifest.provides,
                "trust": self.context.security.get_trust_level(manifest.id, manifest),
                "capabilities": manifest.capabilities,
                "blocked": self.blocked.get(manifest.id),
                "health": health,
            })
        return descriptions
