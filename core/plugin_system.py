from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.audit import AuditLogger
from core.approval import ApprovalRegistry
from core.contracts.kea_status_provider import KeaStatusProvider
from core.contracts.metrics_provider import MetricsProvider
from core.contracts.notification_provider import NotificationProvider
from core.event_bus import EventBus
from core.lifecycle import LifecycleRegistry
from core.manifest_normalizer import normalize_manifest
from core.manifest_validator import validate_manifest, validation_warnings
from core.models.plugin_manifest import PluginManifestV1
from core.plugin_api import DashboardPlugin, PluginEvent
from core.quarantine import QuarantineRegistry
from core.reviews import ReviewRegistry
from core.security import SecurityManager
from server.scheduler import Scheduler

SERVICE_CONTRACTS = {
    "notifier.home_assistant": NotificationProvider,
    "metrics.prometheus": MetricsProvider,
    "kea.ha": KeaStatusProvider,
}


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
        self._current_manifest_obj: Optional[PluginManifestV1] = None
        self._plugin_manifests: Dict[str, PluginManifestV1] = {}
        self.security = SecurityManager(self.root_dir, config)
        self.audit: Optional[AuditLogger] = None

    @property
    def config(self) -> dict:
        return self._root_config

    def set_current_plugin(self, plugin_id: Optional[str]) -> None:
        self._current_plugin = plugin_id

    def set_current_manifest(self, manifest: Optional[PluginManifestV1]) -> None:
        self._current_manifest_obj = manifest

    def bind_plugin_manifest(self, plugin_id: str, manifest: PluginManifestV1) -> None:
        self._plugin_manifests[plugin_id] = manifest

    def _manifest_for(self, plugin_id: Optional[str]) -> Optional[PluginManifestV1]:
        if plugin_id is None:
            return self._current_manifest_obj
        return self._plugin_manifests.get(plugin_id, self._current_manifest_obj)

    def _wrap_with_plugin_context(self, plugin_id: Optional[str], manifest: Optional[PluginManifestV1], fn):
        def wrapped(*args, **kwargs):
            prev_plugin = self._current_plugin
            prev_manifest = self._current_manifest_obj
            self._current_plugin = plugin_id
            self._current_manifest_obj = manifest
            try:
                return fn(*args, **kwargs)
            finally:
                self._current_plugin = prev_plugin
                self._current_manifest_obj = prev_manifest
        return wrapped

    def require_permission(self, permission: str):
        manifest = self._manifest_for(self._current_plugin)
        plugin_id = self._current_plugin or getattr(manifest, "id", "unknown")
        if manifest is None:
            raise RuntimeError("No manifest available for permission check")

        try:
            self.security.require(plugin_id, manifest, permission)
            if self.audit:
                self.audit.log(plugin_id, permission, "permission_check", None, "allowed")
        except Exception:
            if self.audit:
                self.audit.log(plugin_id, permission, "permission_check", None, "denied")
            raise

    def require_capability(self, capability: str):
        self.require_permission(capability)

    def get_plugin_config(self, plugin_id: str) -> dict:
        return self._root_config.get("plugins", {}).get(plugin_id, {})

    def _validate_service_contract(self, name: str, service: Any):
        contract = SERVICE_CONTRACTS.get(name)
        if contract is None:
            return
        missing = []
        for attr, value in contract.__dict__.items():
            if attr.startswith("_"):
                continue
            if callable(value) and not hasattr(service, attr):
                missing.append(attr)
        if missing:
            raise TypeError(f"Service {name} missing contract members: {', '.join(missing)}")

    def register_service(self, name: str, service: Any) -> None:
        manifest = self._current_manifest_obj
        if self._current_plugin and manifest is not None:
            if name not in manifest.provides:
                raise PermissionError(f"{manifest.id} attempted undeclared service export: {name}")
            if name in self.services and self.service_owners.get(name) != self._current_plugin:
                raise RuntimeError(f"Service already registered by another owner: {name}")
            self._validate_service_contract(name, service)

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
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin
        methods = list(methods or ["GET"])
        if manifest is None:
            raise RuntimeError("No current manifest bound during route registration")

        declared = {(r.path, tuple(m.upper() for m in r.methods)) for r in manifest.contributes.routes}
        candidate = (path, tuple(m.upper() for m in methods))
        if candidate not in declared:
            raise PermissionError(f"{manifest.id} attempted undeclared route registration: {path} {methods}")

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.routes.append(RouteRegistration(path=path, methods=methods, handler=wrapped, plugin_id=plugin_id))

    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin
        if manifest is None:
            raise RuntimeError("No current manifest bound during card registration")

        declared = {(c.id, c.title, c.order) for c in manifest.contributes.dashboard_cards}
        if (card_id, title, order) not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared dashboard card registration: {card_id} / {title} / {order}"
            )

        wrapped_render = self._wrap_with_plugin_context(plugin_id, manifest, render) if render else None
        self.cards.append(DashboardCard(id=card_id, title=title, render=wrapped_render, order=order, plugin_id=plugin_id))

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin
        if manifest is None:
            raise RuntimeError("No current manifest bound during event subscription")

        declared = set(manifest.contributes.consumes_events)
        if event_type == "*":
            if manifest.trust_level not in {"trusted", "core"}:
                raise PermissionError(f"{manifest.id} may not subscribe to wildcard events")
            if "*" not in declared:
                raise PermissionError(f"{manifest.id} did not declare wildcard event consumption")
        elif event_type not in declared:
            raise PermissionError(f"{manifest.id} attempted undeclared event subscription: {event_type}")

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.event_bus.subscribe(event_type, wrapped, owner=plugin_id)

    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        manifest = self._manifest_for(self._current_plugin)
        if manifest is not None:
            declared = set(manifest.contributes.produces_events)
            if event_type not in declared:
                raise PermissionError(f"{manifest.id} attempted undeclared event emission: {event_type}")

        self.event_bus.emit(
            PluginEvent(
                type=event_type,
                source=self._current_plugin or "system",
                payload=payload or {},
                severity=severity,
            )
        )


class PluginManager:
    def __init__(self, *, root_dir: Path, config: dict, plugins_dir: str = "plugins") -> None:
        self.root_dir = Path(root_dir)
        self.plugins_dir = self.root_dir / plugins_dir
        self.config = config
        self.event_bus = EventBus(logging.getLogger("ukd.events"))
        self.scheduler = Scheduler(logging.getLogger("ukd.scheduler"))
        self.context = PluginContext(root_dir=self.root_dir, config=config, event_bus=self.event_bus)
        self.context.register_service("scheduler", self.scheduler)
        self.context.register_service("event_bus", self.event_bus)
        self.context.register_service("plugin_manager", self)

        self.audit = AuditLogger(self.root_dir)
        self.context.audit = self.audit
        self.review_registry = ReviewRegistry(self.root_dir)
        self.approval_registry = ApprovalRegistry(self.root_dir)
        self.quarantine_registry = QuarantineRegistry(self.root_dir)
        self.lifecycle = LifecycleRegistry()

        self.manifests: Dict[str, PluginManifestV1] = {}
        self.plugins: Dict[str, Any] = {}
        self.blocked: Dict[str, str] = {}
        self.logger = logging.getLogger("ukd.plugins")
        self.state_file = self.plugins_dir / ".state.json"
        self.plugin_state = self._load_state()
        self.failure_counts: Dict[str, int] = {}

    def _load_state(self) -> Dict[str, bool]:
        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return {}

    def _save_state(self) -> None:
        self.state_file.write_text(json.dumps(self.plugin_state, indent=2))

    def discover(self) -> Dict[str, PluginManifestV1]:
        manifests: Dict[str, PluginManifestV1] = {}
        for path in self.plugins_dir.glob("*/manifest.json"):
            try:
                raw = json.loads(path.read_text())
                raw, warnings = normalize_manifest(raw)
                manifest = PluginManifestV1.from_dict(raw)
                for warning in warnings + validation_warnings(manifest):
                    self.logger.warning("Manifest %s: %s", manifest.id, warning)

                errors = validate_manifest(manifest)
                errors.extend(self.context.security.validate_permissions(manifest.id, manifest))
                review = self.review_registry.get(manifest.id)
                review_state = review.get("review_state", "unapproved")
                if not self.context.security.policy.is_review_state_allowed(review_state):
                    errors.append(f"review state {review_state} not allowed in runtime mode")

                if errors:
                    self.blocked[manifest.id] = "; ".join(errors)
                    self.logger.warning("Blocked plugin %s: %s", manifest.id, self.blocked[manifest.id])
                    self.lifecycle.set(manifest.id, "blocked")
                    continue

                manifests[manifest.id] = manifest
                self.lifecycle.set(manifest.id, "validated")
            except Exception:
                self.logger.exception("Failed manifest load: %s", path)

        self.manifests = manifests
        return manifests

    def _resolve_load_order(self) -> list[str]:
        manifests = self.manifests
        visited: Dict[str, str] = {}
        order: List[str] = []

        def visit(pid: str):
            state = visited.get(pid)
            if state == "temp":
                raise ValueError(f"Dependency cycle detected at {pid}")
            if state == "perm":
                return
            if pid not in manifests:
                raise ValueError(f"Missing dependency: {pid}")

            visited[pid] = "temp"
            for dep in manifests[pid].depends_on:
                visit(dep)
            visited[pid] = "perm"
            order.append(pid)

        for pid in manifests:
            visit(pid)

        return order

    def _check_required_services(self, manifest: PluginManifestV1) -> list[str]:
        missing = []
        for name in manifest.requires_services:
            if self.context.get_service(name) is None:
                missing.append(name)
        return missing

    def _load_module(self, manifest: PluginManifestV1):
        module_path, _, class_name = manifest.entrypoint.partition(":")
        file_path = self.plugins_dir / manifest.id / f"{module_path}.py"
        spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}", file_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return getattr(module, class_name)

    def _load_single_plugin(self, pid: str, manifest: PluginManifestV1) -> bool:
        self.lifecycle.set(pid, "loading")
        if pid in self.plugins:
            self.lifecycle.set(pid, "running")
            return True

        missing = self._check_required_services(manifest)
        if missing:
            reason = f"missing required services: {', '.join(missing)}"
            self.blocked[pid] = reason
            self.lifecycle.set(pid, "blocked")
            self.logger.warning("Blocked plugin %s: %s", pid, reason)
            return False

        try:
            cls = self._load_module(manifest)
            plugin = cls()
            plugin.manifest = manifest

            self.context.bind_plugin_manifest(pid, manifest)
            self.context.set_current_plugin(pid)
            self.context.set_current_manifest(manifest)
            try:
                if hasattr(plugin, "setup"):
                    plugin.setup(self.context)
                else:
                    plugin.register(self.context)
            finally:
                self.context.set_current_plugin(None)
                self.context.set_current_manifest(None)

            self.plugins[pid] = plugin
            self.context.services[pid] = plugin
            self.context.service_owners[pid] = pid

            self.blocked.pop(pid, None)
            self.failure_counts[pid] = 0
            self.lifecycle.set(pid, "loaded")
            return True
        except Exception as exc:
            self.failure_counts[pid] = self.failure_counts.get(pid, 0) + 1
            self.blocked[pid] = str(exc)
            if self.failure_counts[pid] >= 5:
                self.quarantine_registry.quarantine(pid, str(exc))
                self.lifecycle.set(pid, "quarantined")
            else:
                self.lifecycle.set(pid, "failed")
            self.logger.exception("Failed plugin %s", pid)
            return False

    def load_enabled_plugins(self):
        try:
            load_order = self._resolve_load_order()
        except Exception as exc:
            self.logger.exception("Failed to resolve plugin load order")
            for pid in self.manifests:
                self.blocked[pid] = f"dependency resolution failed: {exc}"
                self.lifecycle.set(pid, "blocked")
            return

        for pid in load_order:
            if self.quarantine_registry.is_quarantined(pid):
                self.blocked[pid] = "quarantined"
                self.lifecycle.set(pid, "quarantined")
                continue

            manifest = self.manifests[pid]
            enabled = self.plugin_state.get(pid, manifest.enabled_by_default)
            if enabled:
                self._load_single_plugin(pid, manifest)
            else:
                self.lifecycle.set(pid, "disabled")

    def start_all(self):
        for pid, plugin in self.plugins.items():
            try:
                plugin.start()
                self.lifecycle.set(pid, "running")
            except Exception:
                self.logger.exception("Start failed %s", pid)
                self.lifecycle.set(pid, "failed")

    def stop_all(self):
        self.scheduler.cancel_all()
        for pid, plugin in reversed(list(self.plugins.items())):
            try:
                plugin.stop()
                self.lifecycle.set(pid, "stopped")
            except Exception:
                self.logger.exception("Stop failed %s", pid)
                self.lifecycle.set(pid, "failed")

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
        self.lifecycle.set(plugin_id, "stopped")
        return True

    def enable_plugin(self, plugin_id: str) -> bool:
        manifest = self.manifests.get(plugin_id)
        if not manifest:
            return False
        self.plugin_state[plugin_id] = True
        self._save_state()
        ok = self._load_single_plugin(plugin_id, manifest)
        if ok:
            plugin = self.plugins.get(plugin_id)
            if plugin:
                try:
                    plugin.start()
                    self.lifecycle.set(plugin_id, "running")
                except Exception:
                    self.logger.exception("Start failed %s", plugin_id)
                    self.lifecycle.set(plugin_id, "failed")
                    return False
        return ok

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
                "permissions": manifest.permissions,
                "blocked": self.blocked.get(manifest.id),
                "health": health,
                "lifecycle": self.lifecycle.get(manifest.id),
            })
        return descriptions
