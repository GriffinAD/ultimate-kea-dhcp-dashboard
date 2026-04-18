#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

if [ ! -d .git ]; then
  echo "Run this from the repository root (or pass the repo path)." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "plugin" ]; then
  echo "Current branch is '$branch'. Switch to 'plugin' first." >&2
  exit 1
fi

mkdir -p core/models core/contracts plugins/core_enhancements

cat > core/models/__init__.py <<'PY'
from .plugin_manifest import (
    RouteContribution,
    DashboardCardContribution,
    ScheduledJobContribution,
    PluginContributions,
    PluginManifestV1,
)
PY

cat > core/models/plugin_manifest.py <<'PY'
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RouteContribution:
    path: str
    methods: list[str] = field(default_factory=lambda: ["GET"])
    auth: str = "admin"


@dataclass(slots=True)
class DashboardCardContribution:
    id: str
    title: str
    slot: str = "dashboard.main"
    order: int = 100


@dataclass(slots=True)
class ScheduledJobContribution:
    name: str
    interval_seconds: int


@dataclass(slots=True)
class PluginContributions:
    routes: list[RouteContribution] = field(default_factory=list)
    dashboard_cards: list[DashboardCardContribution] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    scheduled_jobs: list[ScheduledJobContribution] = field(default_factory=list)
    consumes_events: list[str] = field(default_factory=list)
    produces_events: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PluginManifestV1:
    id: str
    name: str
    version: str
    plugin_api_version: str
    entrypoint: str
    enabled_by_default: bool = True
    description: str = ""
    publisher: str = "local"
    trust_level: str = "local"
    permissions: list[str] = field(default_factory=list)
    contributes: PluginContributions = field(default_factory=PluginContributions)
    requires_services: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    config_schema: str | None = None
    ui_entrypoint: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifestV1":
        contrib = data.get("contributes", {}) or {}

        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            version=data.get("version", "0.1.0"),
            plugin_api_version=data.get("plugin_api_version", "1.0"),
            entrypoint=data["entrypoint"],
            enabled_by_default=data.get("enabled_by_default", True),
            description=data.get("description", ""),
            publisher=data.get("publisher", "local"),
            trust_level=data.get("trust_level", "local"),
            permissions=list(data.get("permissions", [])),
            contributes=PluginContributions(
                routes=[RouteContribution(**r) for r in contrib.get("routes", [])],
                dashboard_cards=[
                    DashboardCardContribution(**c)
                    for c in contrib.get("dashboard_cards", [])
                ],
                services=list(contrib.get("services", [])),
                scheduled_jobs=[
                    ScheduledJobContribution(**j)
                    for j in contrib.get("scheduled_jobs", [])
                ],
                consumes_events=list(contrib.get("consumes_events", [])),
                produces_events=list(contrib.get("produces_events", [])),
            ),
            requires_services=list(data.get("requires_services", [])),
            depends_on=list(data.get("depends_on", [])),
            provides=list(data.get("provides", [])),
            config_schema=data.get("config_schema"),
            ui_entrypoint=data.get("ui_entrypoint"),
        )
PY

cat > core/manifest_normalizer.py <<'PY'
LEGACY_CAPABILITY_MAP = {
    "network_outbound": "network.outbound",
    "plugin_control": "plugin.control",
    "marketplace_install": "plugin.install",
    "destructive": "system.destructive",
}


def normalize_manifest(data: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    normalized = dict(data)

    if "plugin_api_version" not in normalized:
        normalized["plugin_api_version"] = "1.0"
        warnings.append("Manifest missing plugin_api_version; defaulted to 1.0")

    if "permissions" not in normalized:
        permissions = []
        capabilities = normalized.get("capabilities", {}) or {}
        for key, value in capabilities.items():
            if value and key in LEGACY_CAPABILITY_MAP:
                permissions.append(LEGACY_CAPABILITY_MAP[key])
        normalized["permissions"] = permissions
        if capabilities:
            warnings.append("Legacy capabilities converted to permissions; update manifest to v1")

    normalized.setdefault("contributes", {})
    normalized.setdefault("requires_services", [])
    normalized.setdefault("depends_on", [])
    normalized.setdefault("provides", [])

    return normalized, warnings
PY

cat > core/manifest_validator.py <<'PY'
PLUGIN_API_VERSION = "1.0"


def _major(version: str) -> str:
    return version.split(".", 1)[0]


def validate_manifest(manifest) -> list[str]:
    errors = []

    if not manifest.id:
        errors.append("Missing plugin id")

    if not manifest.entrypoint:
        errors.append("Missing entrypoint")

    if not manifest.plugin_api_version:
        errors.append("Missing plugin_api_version")
    elif _major(manifest.plugin_api_version) != _major(PLUGIN_API_VERSION):
        errors.append(
            f"Incompatible plugin_api_version: {manifest.plugin_api_version} "
            f"(runtime supports {PLUGIN_API_VERSION})"
        )

    if manifest.trust_level not in {"local", "trusted", "core"}:
        errors.append(f"Invalid trust_level: {manifest.trust_level}")

    for permission in manifest.permissions:
        if "." not in permission:
            errors.append(f"Invalid permission name: {permission}")

    for route in manifest.contributes.routes:
        valid_prefixes = [f"/api/plugins/{manifest.id}/"]
        if manifest.trust_level == "core":
            valid_prefixes.append("/api/")
        if not any(route.path.startswith(prefix) for prefix in valid_prefixes):
            errors.append(f"Invalid route path: {route.path}")
        if not route.methods:
            errors.append(f"Route missing methods: {route.path}")

    for provided in manifest.provides:
        if "." not in provided and provided not in {"scheduler", "plugin_manager", "event_bus"}:
            errors.append(f"Invalid provided service name: {provided}")

    for required in manifest.requires_services:
        if "." not in required and required not in {"scheduler", "plugin_manager", "event_bus"}:
            errors.append(f"Invalid required service name: {required}")

    if manifest.id == "admin":
        if manifest.publisher != "core" or manifest.trust_level != "core":
            errors.append("admin plugin must be publisher=core and trust_level=core")

    return errors


def validation_warnings(manifest) -> list[str]:
    warnings = []
    sensitive = {"network.outbound", "system.exec", "integration.home_assistant"}
    if sensitive.intersection(set(manifest.permissions)) and not manifest.config_schema:
        warnings.append(f"{manifest.id} has sensitive permissions but no config_schema")
    return warnings
PY

cat > core/contracts/__init__.py <<'PY'
from .alert_provider import AlertProvider
from .notification_provider import NotificationProvider
from .metrics_provider import MetricsProvider
from .kea_status_provider import KeaStatusProvider
from .ui_contribution_provider import UiContributionProvider
from .automation_action_provider import AutomationActionProvider
PY

cat > core/contracts/alert_provider.py <<'PY'
from typing import Protocol, Any


class AlertProvider(Protocol):
    def send_alert(self, level: str, message: str, payload: dict[str, Any] | None = None) -> None: ...
PY

cat > core/contracts/notification_provider.py <<'PY'
from typing import Protocol, Any


class NotificationProvider(Protocol):
    def notify(self, event_name: str, payload: dict[str, Any]) -> dict[str, Any]: ...
PY

cat > core/contracts/metrics_provider.py <<'PY'
from typing import Protocol


class MetricsProvider(Protocol):
    def render_metrics(self) -> str: ...
PY

cat > core/contracts/kea_status_provider.py <<'PY'
from typing import Protocol, Any


class KeaStatusProvider(Protocol):
    def get_status(self) -> dict[str, Any]: ...
PY

cat > core/contracts/ui_contribution_provider.py <<'PY'
from typing import Protocol, Any


class UiContributionProvider(Protocol):
    def register_ui(self, context: Any) -> None: ...
PY

cat > core/contracts/automation_action_provider.py <<'PY'
from typing import Protocol, Any


class AutomationActionProvider(Protocol):
    def execute_action(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]: ...
PY

cat > core/security.py <<'PY'
import json
from pathlib import Path


class SecurityManager:
    TRUST_LEVELS = {"local", "trusted", "core"}

    PERMISSION_RULES = {
        "network.outbound": {"trusted", "core"},
        "network.inbound": {"core"},
        "network.scan": {"trusted", "core"},
        "plugin.control": {"trusted", "core"},
        "plugin.install": {"core"},
        "plugin.disable": {"trusted", "core"},
        "plugin.reload": {"trusted", "core"},
        "system.exec": {"trusted", "core"},
        "system.files.read": {"trusted", "core"},
        "system.files.write": {"trusted", "core"},
        "system.destructive": {"core"},
        "kea.read": {"local", "trusted", "core"},
        "kea.write": {"trusted", "core"},
        "kea.ha.control": {"trusted", "core"},
        "integration.home_assistant": {"trusted", "core"},
        "integration.webhook": {"trusted", "core"},
        "integration.prometheus": {"trusted", "core"},
        "integration.mobile_push": {"trusted", "core"},
        "secret.read": {"trusted", "core"},
        "secret.write": {"core"},
    }

    def __init__(self, root_dir, config=None):
        self.root_dir = Path(root_dir)
        self.config = config or {}
        self.trusted_plugins_path = self.root_dir / "core" / "registry" / "trusted_plugins.json"
        self.trusted_plugins = self._load_trusted_plugins()

    def _load_trusted_plugins(self):
        try:
            data = json.loads(self.trusted_plugins_path.read_text())
            return set(data)
        except Exception:
            return set()

    def _manifest_value(self, manifest, name, default=None):
        if manifest is None:
            return default
        if isinstance(manifest, dict):
            return manifest.get(name, default)
        return getattr(manifest, name, default)

    def get_trust_level(self, plugin_id, manifest):
        if plugin_id in self.trusted_plugins:
            return "trusted"

        publisher = self._manifest_value(manifest, "publisher")
        if publisher == "core":
            return "core"

        declared = self._manifest_value(manifest, "trust_level", "local")
        return declared if declared in self.TRUST_LEVELS else "local"

    def get_permissions(self, manifest):
        permissions = self._manifest_value(manifest, "permissions", []) or []
        return set(permissions)

    def validate_permissions(self, plugin_id, manifest):
        trust = self.get_trust_level(plugin_id, manifest)
        permissions = self.get_permissions(manifest)

        errors = []
        for permission in permissions:
            allowed_trusts = self.PERMISSION_RULES.get(permission)
            if allowed_trusts is None:
                errors.append(f"Unknown permission: {permission}")
                continue
            if trust not in allowed_trusts:
                errors.append(
                    f"{plugin_id} trust level {trust} insufficient for {permission}"
                )
        return errors

    def require(self, plugin_id, manifest, permission):
        permissions = self.get_permissions(manifest)
        if permission not in permissions:
            raise PermissionError(f"{plugin_id} missing permission: {permission}")

        trust = self.get_trust_level(plugin_id, manifest)
        allowed_trusts = self.PERMISSION_RULES.get(permission)
        if allowed_trusts is None:
            raise PermissionError(f"{plugin_id} requested unknown permission: {permission}")

        if trust not in allowed_trusts:
            raise PermissionError(
                f"{plugin_id} trust level {trust} insufficient for {permission}"
            )
PY

cat > core/plugin_system.py <<'PY'
from __future__ import annotations

import importlib.util
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from core.contracts.kea_status_provider import KeaStatusProvider
from core.contracts.metrics_provider import MetricsProvider
from core.contracts.notification_provider import NotificationProvider
from core.event_bus import EventBus
from core.manifest_normalizer import normalize_manifest
from core.manifest_validator import validate_manifest, validation_warnings
from core.models.plugin_manifest import PluginManifestV1
from core.plugin_api import DashboardPlugin, PluginEvent
from core.security import SecurityManager
from server.scheduler import Scheduler

DashboardPlugin = DashboardPlugin

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
        self.security = SecurityManager(self.root_dir, config)

    @property
    def config(self) -> dict:
        return self._root_config

    def set_current_plugin(self, plugin_id: Optional[str]) -> None:
        self._current_plugin = plugin_id

    def set_current_manifest(self, manifest: Optional[PluginManifestV1]) -> None:
        self._current_manifest_obj = manifest

    def require_permission(self, permission: str):
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin or getattr(manifest, "id", "unknown")
        if manifest is None:
            raise RuntimeError("No manifest available for permission check")
        self.security.require(plugin_id, manifest, permission)

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
                raise PermissionError(
                    f"{manifest.id} attempted undeclared service export: {name}"
                )
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
        methods = list(methods or ["GET"])
        if manifest is None:
            raise RuntimeError("No current manifest bound during route registration")

        declared = {(r.path, tuple(m.upper() for m in r.methods)) for r in manifest.contributes.routes}
        candidate = (path, tuple(m.upper() for m in methods))

        if candidate not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared route registration: {path} {methods}"
            )

        self.routes.append(
            RouteRegistration(path=path, methods=methods, handler=handler, plugin_id=self._current_plugin)
        )

    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
        manifest = self._current_manifest_obj
        if manifest is None:
            raise RuntimeError("No current manifest bound during card registration")

        declared = {(c.id, c.title, c.order) for c in manifest.contributes.dashboard_cards}
        if (card_id, title, order) not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared dashboard card registration: "
                f"{card_id} / {title} / {order}"
            )

        self.cards.append(
            DashboardCard(id=card_id, title=title, render=render, order=order, plugin_id=self._current_plugin)
        )

    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
        manifest = self._current_manifest_obj
        if manifest is None:
            raise RuntimeError("No current manifest bound during event subscription")

        declared = set(manifest.contributes.consumes_events)
        if event_type == "*":
            if manifest.trust_level not in {"trusted", "core"}:
                raise PermissionError(f"{manifest.id} may not subscribe to wildcard events")
            if "*" not in declared:
                raise PermissionError(f"{manifest.id} did not declare wildcard event consumption")
        elif event_type not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared event subscription: {event_type}"
            )

        self.event_bus.subscribe(event_type, handler, owner=self._current_plugin)

    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        manifest = self._current_manifest_obj
        if manifest is not None:
            declared = set(manifest.contributes.produces_events)
            if event_type not in declared:
                raise PermissionError(
                    f"{manifest.id} attempted undeclared event emission: {event_type}"
                )

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
        self.manifests: Dict[str, PluginManifestV1] = {}
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

    def discover(self) -> Dict[str, PluginManifestV1]:
        manifests: Dict[str, PluginManifestV1] = {}
        for manifest_path in self.plugins_dir.glob("*/manifest.json"):
            try:
                raw = json.loads(manifest_path.read_text())
                raw, warnings = normalize_manifest(raw)
                manifest = PluginManifestV1.from_dict(raw)
                for warning in warnings + validation_warnings(manifest):
                    self.logger.warning("Manifest %s: %s", manifest.id, warning)
                errors = validate_manifest(manifest)
                errors.extend(self.context.security.validate_permissions(manifest.id, manifest))
                if errors:
                    self.blocked[manifest.id] = "; ".join(errors)
                    self.logger.warning("Blocked plugin %s: %s", manifest.id, self.blocked[manifest.id])
                    continue
                manifests[manifest.id] = manifest
            except Exception:
                self.logger.exception("Failed to parse %s", manifest_path)
        self.manifests = manifests
        return manifests

    def _resolve_load_order(self) -> list[str]:
        manifests = self.manifests
        visited = {}
        order = []

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

    def _check_required_services(self, manifest) -> list[str]:
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
        if pid in self.plugins:
            return True

        missing_services = self._check_required_services(manifest)
        if missing_services:
            reason = f"missing required services: {', '.join(missing_services)}"
            self.blocked[pid] = reason
            self.logger.warning("Blocked plugin %s: %s", pid, reason)
            return False

        try:
            cls = self._load_module(manifest)
            plugin = cls()
            plugin.manifest = manifest

            self.context.set_current_plugin(pid)
            self.context.set_current_manifest(manifest)
            if hasattr(plugin, "setup"):
                plugin.setup(self.context)
            else:
                plugin.register(self.context)
            self.context.set_current_plugin(None)
            self.context.set_current_manifest(None)

            self.plugins[pid] = plugin
            self.context.services[pid] = plugin
            self.context.service_owners[pid] = pid

            try:
                plugin.start()
            except Exception:
                self.logger.exception("Start failed %s", pid)

            self.blocked.pop(pid, None)
            self.logger.info("Loaded %s", pid)
            return True
        except Exception as exc:
            self.context.set_current_plugin(None)
            self.context.set_current_manifest(None)
            self.blocked[pid] = str(exc)
            self.logger.exception("Failed plugin %s", pid)
            return False

    def load_enabled_plugins(self):
        try:
            load_order = self._resolve_load_order()
        except Exception as exc:
            self.logger.exception("Failed to resolve plugin load order")
            for pid in self.manifests:
                self.blocked[pid] = f"dependency resolution failed: {exc}"
            return

        for pid in load_order:
            manifest = self.manifests[pid]
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
                "permissions": manifest.permissions,
                "blocked": self.blocked.get(manifest.id),
                "health": health,
            })
        return descriptions
PY

cat > plugins/admin/manifest.json <<'JSON'
{
  "id": "admin",
  "name": "Plugin Admin",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "description": "Plugin health, status, and recent event visibility",
  "publisher": "core",
  "trust_level": "core",
  "permissions": [
    "plugin.control",
    "plugin.install"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/admin/health", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/alerts", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/plugins", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/plugins/restart", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/admin/plugins/enable", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/admin/plugins/disable", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/admin/marketplace/plugins", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/marketplace/install", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/admin/ui/plugins", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/status", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/events", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/admin/stream", "methods": ["GET"], "auth": "admin" }
    ],
    "dashboard_cards": [
      { "id": "admin_overview", "title": "System Overview", "slot": "dashboard.main", "order": 0 }
    ],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": ["*"],
    "produces_events": []
  },
  "requires_services": ["plugin_manager"],
  "depends_on": [],
  "provides": [
    "plugin.admin",
    "plugin.status"
  ]
}
JSON

cat > plugins/admin/routes.py <<'PY'
def register_routes(context):
    from .services import (
        get_health,
        get_alerts,
        list_plugins,
        list_marketplace_plugins,
        install_marketplace_plugin,
    )

    context.register_route(
        "/api/plugins/admin/health",
        lambda handler: get_health(context),
        methods=["GET"]
    )

    context.register_route(
        "/api/plugins/admin/alerts",
        lambda handler: get_alerts(context),
        methods=["GET"]
    )

    context.register_route(
        "/api/plugins/admin/plugins",
        lambda handler: list_plugins(context),
        methods=["GET"]
    )

    def restart_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        context.require_permission("plugin.control")
        if pm:
            pm.restart_plugin(pid)
            return {"status": "restarted"}
        return {"error": "not found"}

    context.register_route(
        "/api/plugins/admin/plugins/restart",
        restart_plugin,
        methods=["POST"]
    )

    def enable_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        context.require_permission("plugin.control")
        if pm:
            pm.enable_plugin(pid)
            return {"status": "enabled"}
        return {"error": "not found"}

    context.register_route(
        "/api/plugins/admin/plugins/enable",
        enable_plugin,
        methods=["POST"]
    )

    def disable_plugin(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")

        pm = context.get_service("plugin_manager")
        context.require_permission("plugin.control")
        if pm:
            pm.disable_plugin(pid)
            return {"status": "disabled"}
        return {"error": "not found"}

    context.register_route(
        "/api/plugins/admin/plugins/disable",
        disable_plugin,
        methods=["POST"]
    )

    context.register_route(
        "/api/plugins/admin/marketplace/plugins",
        lambda handler: list_marketplace_plugins(context),
        methods=["GET"]
    )

    def install_marketplace(handler):
        import json
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        pid = data.get("plugin")
        context.require_permission("plugin.install")
        return install_marketplace_plugin(context, pid)

    context.register_route(
        "/api/plugins/admin/marketplace/install",
        install_marketplace,
        methods=["POST"]
    )

    def get_ui_plugins(handler=None):
        pm = context.get_service("plugin_manager")
        if not pm:
            return []

        known = {
            "admin": {"route": "/admin", "title": "Admin"},
            "automation_engine": {"route": "/automation", "title": "Automation"},
            "kea_ha": {"route": "/kea", "title": "Kea HA"},
            "home_assistant": {"route": "/home-assistant", "title": "Home Assistant"},
            "prometheus": {"route": "/prometheus", "title": "Prometheus"}
        }

        return [
            {
                "plugin": pid,
                "route": known[pid]["route"],
                "title": known[pid]["title"]
            }
            for pid in pm.plugins.keys()
            if pid in known
        ]

    context.register_route(
        "/api/plugins/admin/ui/plugins",
        get_ui_plugins,
        methods=["GET"]
    )
PY

cat > plugins/home_assistant/manifest.json <<'JSON'
{
  "id": "home_assistant",
  "name": "Home Assistant",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "description": "Send dashboard and HA events to Home Assistant via webhook",
  "publisher": "local",
  "trust_level": "trusted",
  "permissions": [
    "network.outbound",
    "integration.home_assistant"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/home_assistant/test", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/home_assistant/status", "methods": ["GET"], "auth": "admin" }
    ],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": [
      "kea.ha.status",
      "kea.ha.state_changed",
      "kea.ha.failover_detected",
      "kea.ha.partner_down"
    ],
    "produces_events": []
  },
  "requires_services": [],
  "depends_on": [],
  "provides": [
    "notifier.home_assistant"
  ],
  "config_schema": "config.schema.json"
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/home_assistant/plugin.py")
text = p.read_text()
text = text.replace('"/api/plugins/home-assistant/test"', '"/api/plugins/home_assistant/test"')
text = text.replace('"/api/plugins/home-assistant/status"', '"/api/plugins/home_assistant/status"')
text = text.replace('context.event_bus.subscribe("kea.ha.status", self.handle_ha_status)', 'context.subscribe("kea.ha.status", self.handle_ha_status)')
text = text.replace('context.event_bus.subscribe("kea.ha.state_changed", self.handle_state_changed)', 'context.subscribe("kea.ha.state_changed", self.handle_state_changed)')
text = text.replace('context.event_bus.subscribe("kea.ha.failover_detected", self.handle_failover)', 'context.subscribe("kea.ha.failover_detected", self.handle_failover)')
text = text.replace('context.event_bus.subscribe("kea.ha.partner_down", self.handle_partner_down)', 'context.subscribe("kea.ha.partner_down", self.handle_partner_down)')
text = text.replace('response = requests.post(destination, json=payload, timeout=3)', 'self.context.require_permission("network.outbound")\n                response = requests.post(destination, json=payload, timeout=3)')
p.write_text(text)
PY

cat > plugins/kea_ha/manifest.json <<'JSON'
{
  "id": "kea_ha",
  "name": "Kea HA",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "description": "Kea High Availability monitoring",
  "publisher": "local",
  "trust_level": "trusted",
  "permissions": [
    "network.outbound",
    "kea.read"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/kea_ha/status", "methods": ["GET"], "auth": "admin" }
    ],
    "dashboard_cards": [
      { "id": "kea_ha_status", "title": "Kea HA Status", "slot": "dashboard.main", "order": 10 }
    ],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": [],
    "produces_events": [
      "kea.ha.status",
      "kea.ha.state_changed",
      "kea.ha.failover_detected",
      "kea.ha.partner_down"
    ]
  },
  "requires_services": ["scheduler"],
  "depends_on": [],
  "provides": ["kea.ha"],
  "config_schema": "config.schema.json"
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/kea_ha/plugin.py")
text = p.read_text()
text = text.replace('"/api/plugins/kea-ha/status"', '"/api/plugins/kea_ha/status"')
text = text.replace('self.context.event_bus.emit(PluginEvent(\n            type="kea.ha.status",\n            source="kea_ha",\n            payload=deepcopy(cluster_status)\n        ))', 'self.context.emit("kea.ha.status", deepcopy(cluster_status))')
text = text.replace('self.context.event_bus.emit(PluginEvent(\n                type="kea.ha.state_changed",\n                source="kea_ha",\n                payload={\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                }\n            ))', 'self.context.emit("kea.ha.state_changed", {\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                })')
text = text.replace('self.context.event_bus.emit(PluginEvent(\n                type="kea.ha.failover_detected",\n                source="kea_ha",\n                payload={\n                    "from": previous_active,\n                    "to": current_active,\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                }\n            ))', 'self.context.emit("kea.ha.failover_detected", {\n                    "from": previous_active,\n                    "to": current_active,\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                })')
text = text.replace('self.context.event_bus.emit(PluginEvent(\n                type="kea.ha.partner_down",\n                source="kea_ha",\n                payload={\n                    "nodes": sorted(current_partner_down),\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                }\n            ))', 'self.context.emit("kea.ha.partner_down", {\n                    "nodes": sorted(current_partner_down),\n                    "previous": deepcopy(previous),\n                    "current": deepcopy(cluster_status),\n                })')
text = text.replace('response = requests.post(', 'self.context.require_permission("network.outbound")\n                response = requests.post(')
text = text.replace('from core.plugin_api import DashboardPlugin, PluginEvent', 'from core.plugin_api import DashboardPlugin')
p.write_text(text)
PY

cat > plugins/automation/manifest.json <<'JSON'
{
  "id": "automation",
  "name": "Automation",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "description": "Executes automation actions for HA failover and partner-down events",
  "publisher": "local",
  "trust_level": "trusted",
  "permissions": [
    "network.outbound",
    "system.exec"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/automation/status", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/automation/rules", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/automation/rules", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/automation/test", "methods": ["POST"], "auth": "admin" }
    ],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": ["*"],
    "produces_events": ["automation.notify"]
  },
  "requires_services": [],
  "depends_on": [],
  "provides": ["automation.engine"],
  "config_schema": "config.schema.json"
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/automation/plugin.py")
text = p.read_text()
text = text.replace('        self._subscribe_rules()\n', '        context.subscribe("*", self._handle_event)\n')
text = text.replace('    def _subscribe_rules(self):\n        seen = set()\n        for rule in self.rules:\n            event_type = rule.get("when")\n            if event_type and event_type not in seen:\n                self.context.subscribe(event_type, self._handle_event)\n                seen.add(event_type)\n\n', '')
text = text.replace('        self._subscribe_rules()\n', '')
text = text.replace('        response = requests.post(url, json=payload, timeout=3)', '        self.context.require_permission("network.outbound")\n        response = requests.post(url, json=payload, timeout=3)')
text = text.replace('        subprocess.Popen(command, shell=True)', '        self.context.require_permission("system.exec")\n        subprocess.Popen(command, shell=True)')
p.write_text(text)
PY

cat > plugins/automation_engine/manifest.json <<'JSON'
{
  "id": "automation_engine",
  "name": "Automation Engine",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "publisher": "local",
  "trust_level": "trusted",
  "permissions": [
    "network.outbound"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/automation_engine/rules", "methods": ["GET"], "auth": "admin" },
      { "path": "/api/plugins/automation_engine/rules/add", "methods": ["POST"], "auth": "admin" },
      { "path": "/api/plugins/automation_engine/rules/delete", "methods": ["POST"], "auth": "admin" }
    ],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": ["*"],
    "produces_events": []
  },
  "requires_services": [],
  "depends_on": [],
  "provides": ["automation.engine"]
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/automation_engine/plugin.py")
text = p.read_text()
text = text.replace('context.register_route("/api/automation/rules", self.get_rules)', 'context.register_route("/api/plugins/automation_engine/rules", self.get_rules)')
text = text.replace('context.register_route("/api/automation/rules/add", self.add_rule, methods=["POST"])', 'context.register_route("/api/plugins/automation_engine/rules/add", self.add_rule, methods=["POST"])')
text = text.replace('context.register_route("/api/automation/rules/delete", self.delete_rule, methods=["POST"])', 'context.register_route("/api/plugins/automation_engine/rules/delete", self.delete_rule, methods=["POST"])')
p.write_text(text)

u = Path("plugins/automation_engine/ui/index.js")
text = u.read_text()
text = text.replace("/api/automation/rules", "/api/plugins/automation_engine/rules")
text = text.replace("/api/automation/rules/add", "/api/plugins/automation_engine/rules/add")
text = text.replace("/api/automation/rules/delete", "/api/plugins/automation_engine/rules/delete")
u.write_text(text)

a = Path("plugins/automation_engine/actions.py")
text = a.read_text()
text = text.replace('context.security.require("automation_engine", manifest, "network_outbound")', 'context.require_permission("network.outbound")')
a.write_text(text)
PY

cat > plugins/live/manifest.json <<'JSON'
{
  "id": "live",
  "name": "Live Events",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "publisher": "local",
  "trust_level": "trusted",
  "permissions": [],
  "contributes": {
    "routes": [
      { "path": "/api/plugins/live/events", "methods": ["GET"], "auth": "admin" }
    ],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": ["*"],
    "produces_events": []
  },
  "requires_services": [],
  "depends_on": [],
  "provides": ["live.events"]
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/live/plugin.py")
text = p.read_text()
text = text.replace('from core.plugin_system import DashboardPlugin', 'from core.plugin_api import DashboardPlugin')
text = text.replace('        context.event_bus.subscribe("*", self.handle_event)', '        context.subscribe("*", self.handle_event)')
p.write_text(text)
PY

cat > plugins/prometheus/manifest.json <<'JSON'
{
  "id": "prometheus",
  "name": "Prometheus Exporter",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "publisher": "core",
  "trust_level": "core",
  "permissions": [
    "integration.prometheus"
  ],
  "contributes": {
    "routes": [
      { "path": "/api/metrics", "methods": ["GET"], "auth": "none" }
    ],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": [],
    "produces_events": []
  },
  "requires_services": [],
  "depends_on": ["kea_ha"],
  "provides": ["metrics.prometheus"]
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/prometheus/plugin.py")
text = p.read_text()
text = text.replace('from core.plugin_system import DashboardPlugin', 'from core.plugin_api import DashboardPlugin')
text = text.replace('context.register_route("/metrics", self.metrics)', 'context.register_route("/api/metrics", self.metrics)')
p.write_text(text)
PY

cat > plugins/core_enhancements/manifest.json <<'JSON'
{
  "id": "core_enhancements",
  "name": "Core Enhancements",
  "version": "1.0.0",
  "plugin_api_version": "1.0",
  "entrypoint": "plugin:Plugin",
  "enabled_by_default": true,
  "publisher": "core",
  "trust_level": "core",
  "permissions": [
    "plugin.control"
  ],
  "contributes": {
    "routes": [],
    "dashboard_cards": [],
    "services": [],
    "scheduled_jobs": [],
    "consumes_events": ["plugin.failure"],
    "produces_events": []
  },
  "requires_services": ["plugin_manager"],
  "depends_on": [],
  "provides": ["core.enhancements"]
}
JSON

python3 - <<'PY'
from pathlib import Path
p = Path("plugins/core_enhancements/plugin.py")
text = p.read_text()
text = text.replace('        self.context = context\n        context.subscribe("plugin.failure", self.on_failure)\n', '        self.context = context\n        super().setup(context)\n        context.subscribe("plugin.failure", self.on_failure)\n')
text = text.replace('        pm = self.context.get_service("plugin_manager")\n', '        self.context.require_permission("plugin.control")\n        pm = self.context.get_service("plugin_manager")\n')
p.write_text(text)
PY

echo
echo "Files updated. Review with:"
echo "  git status"
echo "  git diff --stat"
echo
echo "Then commit:"
echo "  git add ."
echo "  git commit -m \"feat(plugin): lock down plugin capability model\""
