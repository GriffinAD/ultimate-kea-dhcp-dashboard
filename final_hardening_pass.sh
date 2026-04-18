#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

if [ ! -d .git ]; then
  echo "Run from the repository root (or pass the repo path)." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "plugin" ]; then
  echo "Current branch is '$branch'. Switch to 'plugin' first." >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path
import re

p = Path("core/security.py")
text = p.read_text()

if "from core.policy import PolicyEngine" not in text:
    text = text.replace("import json\nfrom pathlib import Path\n", "import json\nfrom pathlib import Path\nfrom core.policy import PolicyEngine\n")

if "self.policy = PolicyEngine" not in text:
    text = text.replace("        self.config = config or {}\n", "        self.config = config or {}\n        self.policy = PolicyEngine(self.config)\n")

old = """    def require(self, plugin_id, manifest, permission):
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
"""
new = """    def require(self, plugin_id, manifest, permission):
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

        if not self.policy.is_permission_allowed(plugin_id, permission):
            raise PermissionError(f"{plugin_id} blocked by policy for permission: {permission}")
"""
if old in text:
    text = text.replace(old, new)

p.write_text(text)

p = Path("core/plugin_system.py")
text = p.read_text()

imports_old = """from core.manifest_normalizer import normalize_manifest
from core.manifest_validator import validate_manifest, validation_warnings
from core.models.plugin_manifest import PluginManifestV1
from core.plugin_api import DashboardPlugin, PluginEvent
from core.security import SecurityManager
from server.scheduler import Scheduler
"""
imports_new = """from core.audit import AuditLogger
from core.approval import ApprovalRegistry
from core.lifecycle import LifecycleRegistry
from core.manifest_normalizer import normalize_manifest
from core.manifest_validator import validate_manifest, validation_warnings
from core.models.plugin_manifest import PluginManifestV1
from core.plugin_api import DashboardPlugin, PluginEvent
from core.quarantine import QuarantineRegistry
from core.reviews import ReviewRegistry
from core.security import SecurityManager
from server.scheduler import Scheduler
"""
if imports_old in text and "AuditLogger" not in text:
    text = text.replace(imports_old, imports_new)

if "self._plugin_manifests" not in text:
    text = text.replace(
        "        self._current_plugin: Optional[str] = None\n        self._current_manifest_obj: Optional[PluginManifestV1] = None\n        self.security = SecurityManager(self.root_dir, config)\n",
        "        self._current_plugin: Optional[str] = None\n        self._current_manifest_obj: Optional[PluginManifestV1] = None\n        self._plugin_manifests: Dict[str, PluginManifestV1] = {}\n        self.security = SecurityManager(self.root_dir, config)\n        self.audit = None\n"
    )

bind_block = """
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

"""
marker = "    def set_current_manifest(self, manifest: Optional[PluginManifestV1]) -> None:\n        self._current_manifest_obj = manifest\n"
if bind_block.strip() not in text:
    text = text.replace(marker, marker + bind_block)

old = """    def require_permission(self, permission: str):
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin or getattr(manifest, "id", "unknown")
        if manifest is None:
            raise RuntimeError("No manifest available for permission check")
        self.security.require(plugin_id, manifest, permission)
"""
new = """    def require_permission(self, permission: str):
        manifest = self._manifest_for(self._current_plugin)
        plugin_id = self._current_plugin or getattr(manifest, "id", "unknown")
        if manifest is None:
            raise RuntimeError("No manifest available for permission check")
        try:
            self.security.require(plugin_id, manifest, permission)
            if self.audit is not None:
                self.audit.log(plugin_id, permission, "permission_check", None, "allowed")
        except Exception:
            if self.audit is not None:
                self.audit.log(plugin_id, permission, "permission_check", None, "denied")
            raise
"""
if old in text:
    text = text.replace(old, new)

old = """    def register_route(self, path: str, handler: Callable[..., Any], methods=None) -> None:
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
"""
new = """    def register_route(self, path: str, handler: Callable[..., Any], methods=None) -> None:
        manifest = self._current_manifest_obj
        methods = list(methods or ["GET"])
        plugin_id = self._current_plugin
        if manifest is None:
            raise RuntimeError("No current manifest bound during route registration")

        declared = {(r.path, tuple(m.upper() for m in r.methods)) for r in manifest.contributes.routes}
        candidate = (path, tuple(m.upper() for m in methods))

        if candidate not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared route registration: {path} {methods}"
            )

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.routes.append(
            RouteRegistration(path=path, methods=methods, handler=wrapped, plugin_id=plugin_id)
        )
"""
if old in text:
    text = text.replace(old, new)

old = """    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
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
"""
new = """    def register_dashboard_card(self, card_id: str, title: str, render=None, order: int = 100) -> None:
        manifest = self._current_manifest_obj
        plugin_id = self._current_plugin
        if manifest is None:
            raise RuntimeError("No current manifest bound during card registration")

        declared = {(c.id, c.title, c.order) for c in manifest.contributes.dashboard_cards}
        if (card_id, title, order) not in declared:
            raise PermissionError(
                f"{manifest.id} attempted undeclared dashboard card registration: "
                f"{card_id} / {title} / {order}"
            )

        wrapped_render = self._wrap_with_plugin_context(plugin_id, manifest, render) if render else None
        self.cards.append(
            DashboardCard(id=card_id, title=title, render=wrapped_render, order=order, plugin_id=plugin_id)
        )
"""
if old in text:
    text = text.replace(old, new)

old = """    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
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
"""
new = """    def subscribe(self, event_type: str, handler: Callable[[PluginEvent], None]) -> None:
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
            raise PermissionError(
                f"{manifest.id} attempted undeclared event subscription: {event_type}"
            )

        wrapped = self._wrap_with_plugin_context(plugin_id, manifest, handler)
        self.event_bus.subscribe(event_type, wrapped, owner=plugin_id)
"""
if old in text:
    text = text.replace(old, new)

old = """    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
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
"""
new = """    def emit(self, event_type: str, payload: dict | None = None, severity: str = "info") -> None:
        manifest = self._manifest_for(self._current_plugin)
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
"""
if old in text:
    text = text.replace(old, new)

if "self.review_registry" not in text:
    text = text.replace(
        "        self.plugin_state = self._load_state()\n",
        "        self.plugin_state = self._load_state()\n        self.audit = AuditLogger(self.root_dir)\n        self.context.audit = self.audit\n        self.review_registry = ReviewRegistry(self.root_dir)\n        self.approval_registry = ApprovalRegistry(self.root_dir)\n        self.quarantine_registry = QuarantineRegistry(self.root_dir)\n        self.lifecycle = LifecycleRegistry()\n"
    )

old = """                errors = validate_manifest(manifest)
                errors.extend(self.context.security.validate_permissions(manifest.id, manifest))
"""
new = """                errors = validate_manifest(manifest)
                errors.extend(self.context.security.validate_permissions(manifest.id, manifest))
                review = self.review_registry.get(manifest.id)
                review_state = review.get("review_state", "unapproved")
                if not self.context.security.policy.is_review_state_allowed(review_state):
                    errors.append(f"review state {review_state} not allowed in runtime mode")
"""
if old in text:
    text = text.replace(old, new)

if 'self.lifecycle.set(manifest.id, "validated")' not in text:
    text = text.replace("                manifests[manifest.id] = manifest\n", "                manifests[manifest.id] = manifest\n                self.lifecycle.set(manifest.id, \"validated\")\n")

old = """    def _load_single_plugin(self, pid: str, manifest: PluginManifestV1) -> bool:
        if pid in self.plugins:
            return True
"""
new = """    def _load_single_plugin(self, pid: str, manifest: PluginManifestV1) -> bool:
        self.lifecycle.set(pid, "loaded")
        if pid in self.plugins:
            return True
"""
if old in text:
    text = text.replace(old, new)

if 'self.context.bind_plugin_manifest(pid, manifest)' not in text:
    text = text.replace("            plugin.manifest = manifest\n\n            self.context.set_current_plugin(pid)\n", "            plugin.manifest = manifest\n            self.context.bind_plugin_manifest(pid, manifest)\n\n            self.context.set_current_plugin(pid)\n")

if 'self.lifecycle.set(pid, "running")' not in text:
    text = text.replace("            self.blocked.pop(pid, None)\n            self.logger.info(\"Loaded %s\", pid)\n            return True\n", "            self.blocked.pop(pid, None)\n            self.lifecycle.set(pid, \"running\")\n            self.logger.info(\"Loaded %s\", pid)\n            return True\n")

if 'self.quarantine_registry.quarantine(pid, str(exc))' not in text:
    text = text.replace("            self.blocked[pid] = str(exc)\n            self.logger.exception(\"Failed plugin %s\", pid)\n            return False\n", "            self.blocked[pid] = str(exc)\n            count = int(getattr(self, 'failure_counts', {}).get(pid, 0)) + 1\n            if not hasattr(self, 'failure_counts'):\n                self.failure_counts = {}\n            self.failure_counts[pid] = count\n            if count >= 5:\n                self.quarantine_registry.quarantine(pid, str(exc))\n                self.lifecycle.set(pid, \"quarantined\")\n            else:\n                self.lifecycle.set(pid, \"failed\")\n            self.logger.exception(\"Failed plugin %s\", pid)\n            return False\n")

if 'self.quarantine_registry.is_quarantined(pid)' not in text:
    text = text.replace("        for pid in load_order:\n", "        for pid in load_order:\n            if self.quarantine_registry.is_quarantined(pid):\n                self.blocked[pid] = \"quarantined\"\n                self.lifecycle.set(pid, \"quarantined\")\n                continue\n")

if '"lifecycle": self.lifecycle.get(manifest.id)' not in text:
    text = text.replace('"health": health,\n            })\n', '"health": health,\n                "lifecycle": self.lifecycle.get(manifest.id),\n            })\n')

p.write_text(text)

# Optional: switch Home Assistant to shared outbound client if enterprise file exists
p = Path("plugins/home_assistant/plugin.py")
if p.exists():
    text = p.read_text()
    if "from core.outbound import OutboundClient" not in text and Path("core/outbound.py").exists():
        text = text.replace("import requests\n", "import requests\nfrom core.outbound import OutboundClient\n")
    if "self.outbound = OutboundClient(context)" not in text:
        text = text.replace("        super().setup(context)\n", "        super().setup(context)\n        self.outbound = OutboundClient(context)\n")
    text = text.replace(
        '                self.context.require_permission("network.outbound")\n                response = requests.post(destination, json=payload, timeout=3)',
        '                response = self.outbound.post_json(self.manifest.id, destination, payload, timeout=3)'
    )
    p.write_text(text)
PY

echo
echo "Final hardening pass applied."
echo "Review with:"
echo "  git diff --stat"
echo "  git diff core/security.py core/plugin_system.py plugins/home_assistant/plugin.py"
echo
echo "Then run your smoke tests and commit."
