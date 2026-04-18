from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.audit import AuditLogger
from core.approval import ApprovalRegistry
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

    def set_current_plugin(self, plugin_id: Optional[str]) -> None:
        self._current_plugin = plugin_id

    def set_current_manifest(self, manifest: Optional[PluginManifestV1]) -> None:
        self._current_manifest_obj = manifest

    def bind_plugin_manifest(self, plugin_id: str, manifest: PluginManifestV1) -> None:
        self._plugin_manifests[plugin_id] = manifest

    def _manifest_for(self, plugin_id: Optional[str]):
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

    def register_route(self, path: str, handler: Callable[..., Any], methods=None) -> None:
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin
        methods = list(methods or ["GET"])

        declared = {(r.path, tuple(m.upper() for m in r.methods)) for r in manifest.contributes.routes}
        candidate = (path, tuple(m.upper() for m in methods))

        if candidate not in declared:
            raise PermissionError(f"{manifest.id} attempted undeclared route registration: {path}")

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.routes.append(RouteRegistration(path=path, methods=methods, handler=wrapped, plugin_id=plugin_id))

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin

        declared = set(manifest.contributes.consumes_events)
        if event_type not in declared and event_type != "*":
            raise PermissionError(f"{manifest.id} attempted undeclared event subscription: {event_type}")

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.event_bus.subscribe(event_type, wrapped, owner=plugin_id)

    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        manifest = self._manifest_for(self._current_plugin)
        if manifest:
            if event_type not in set(manifest.contributes.produces_events):
                raise PermissionError(f"{manifest.id} attempted undeclared event emission: {event_type}")

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

    def discover(self) -> Dict[str, PluginManifestV1]:
        manifests = {}
        for path in self.plugins_dir.glob("*/manifest.json"):
            try:
                raw = json.loads(path.read_text())
                raw, warnings = normalize_manifest(raw)
                manifest = PluginManifestV1.from_dict(raw)

                errors = validate_manifest(manifest)
                errors.extend(self.context.security.validate_permissions(manifest.id, manifest))

                review = self.review_registry.get(manifest.id)
                if not self.context.security.policy.is_review_state_allowed(review.get("review_state", "unapproved")):
                    errors.append("review state not allowed")

                if errors:
                    self.blocked[manifest.id] = "; ".join(errors)
                    continue

                manifests[manifest.id] = manifest
                self.lifecycle.set(manifest.id, "validated")
            except Exception:
                self.logger.exception("Failed manifest load")

        self.manifests = manifests
        return manifests

    def _load_single_plugin(self, pid: str, manifest: PluginManifestV1) -> bool:
        self.lifecycle.set(pid, "loading")
        try:
            cls = self._load_module(manifest)
            plugin = cls()
            plugin.manifest = manifest

            self.context.bind_plugin_manifest(pid, manifest)
            self.context.set_current_plugin(pid)
            self.context.set_current_manifest(manifest)

            if hasattr(plugin, "setup"):
                plugin.setup(self.context)

            self.plugins[pid] = plugin
            self.lifecycle.set(pid, "running")
            return True
        except Exception as exc:
            self.failure_counts[pid] = self.failure_counts.get(pid, 0) + 1
            if self.failure_counts[pid] >= 5:
                self.quarantine_registry.quarantine(pid, str(exc))
                self.lifecycle.set(pid, "quarantined")
            else:
                self.lifecycle.set(pid, "failed")
            return False

    def load_enabled_plugins(self):
        for pid, manifest in self.manifests.items():
            if self.quarantine_registry.is_quarantined(pid):
                self.blocked[pid] = "quarantined"
                self.lifecycle.set(pid, "quarantined")
                continue

            enabled = self.plugin_state.get(pid, manifest.enabled_by_default)
            if enabled:
                self._load_single_plugin(pid, manifest)

    def describe_plugins(self):
        return [{
            "id": m.id,
            "lifecycle": self.lifecycle.get(m.id),
            "blocked": self.blocked.get(m.id)
        } for m in self.manifests.values()]
