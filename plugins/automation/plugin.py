import json
import subprocess
import time
from pathlib import Path
from typing import Any

import requests
from core.plugin_api import DashboardPlugin, PluginEvent


class Plugin(DashboardPlugin):

    def setup(self, context):
        super().setup(context)

        cfg = context.get_plugin_config("automation")

        self.enabled = bool(cfg.get("enabled", context.config.get("automation_enabled", False)))
        self.dry_run = bool(cfg.get("dry_run", context.config.get("automation_dry_run", True)))
        self.cooldown = int(cfg.get("cooldown", context.config.get("automation_cooldown", 60)))
        self.rules_file = Path(self.context.root_dir) / "data" / "automation-rules.json"
        self.rules_file.parent.mkdir(parents=True, exist_ok=True)
        self.rules = self._load_rules(cfg)
        self.last_run = {}
        self.execution_history = []

        self.actions = {
            "webhook": self._action_webhook,
            "command": self._action_command,
            "notify": self._action_notify,
            "emit": self._action_emit,
        }

        context.subscribe("*", self._handle_event)

        context.register_route("/api/plugins/automation/status", self.get_status, ["GET"])
        context.register_route("/api/plugins/automation/rules", self.get_rules, ["GET"])
        context.register_route("/api/plugins/automation/rules", self.save_rules, ["POST"])
        context.register_route("/api/plugins/automation/test", self.test_rule, ["POST"])

        self.set_healthy("Automation ready", rules=len(self.rules), rules_file=str(self.rules_file))

    def _load_rules(self, cfg):
        if self.rules_file.exists():
            try:
                data = json.loads(self.rules_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception as exc:
                self.set_degraded("Failed to load persisted rules", error=str(exc))
        return cfg.get("rules", [])

    def _persist_rules(self):
        self.rules_file.write_text(json.dumps(self.rules, indent=2), encoding="utf-8")

    def get_status(self, handler=None):
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "cooldown": self.cooldown,
            "rules": len(self.rules),
            "rules_file": str(self.rules_file),
            "history": self.execution_history[-20:],
            "health": self.health().__dict__,
        }

    def get_rules(self, handler=None):
        return {
            "rules": self.rules,
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "cooldown": self.cooldown,
        }

    def save_rules(self, handler):
        length = int(handler.headers.get("Content-Length", 0))
        body = handler.rfile.read(length) if length > 0 else b"{}"
        payload = json.loads(body.decode("utf-8"))

        rules = payload.get("rules")
        if not isinstance(rules, list):
            raise ValueError("rules must be a list")

        self.rules = rules
        if "enabled" in payload:
            self.enabled = bool(payload.get("enabled"))
        if "dry_run" in payload:
            self.dry_run = bool(payload.get("dry_run"))
        if "cooldown" in payload:
            self.cooldown = int(payload.get("cooldown"))

        self._persist_rules()
        self.set_healthy("Rules saved", rules=len(self.rules))
        return self.get_rules()

    def test_rule(self, handler):
        length = int(handler.headers.get("Content-Length", 0))
        body = handler.rfile.read(length) if length > 0 else b"{}"
        payload = json.loads(body.decode("utf-8"))

        rule = payload.get("rule")
        event_type = payload.get("event_type") or (rule or {}).get("when") or "automation.test"
        event_payload = payload.get("event_payload") or {}
        event_severity = payload.get("event_severity", "info")

        if not isinstance(rule, dict):
            raise ValueError("rule must be an object")

        event = PluginEvent(
            type=event_type,
            source="admin_test",
            payload=event_payload,
            severity=event_severity,
        )

        matched = self._rule_matches(rule, event)
        actions = self._normalize_actions(rule)
        return {
            "matched": matched,
            "event": {
                "type": event.type,
                "source": event.source,
                "severity": event.severity,
                "payload": event.payload,
            },
            "actions": actions,
        }

    def _cooldown_ok(self, key):
        now = time.time()
        last = self.last_run.get(key, 0)
        if now - last < self.cooldown:
            return False
        self.last_run[key] = now
        return True

    def _handle_event(self, event: PluginEvent):
        if not self.enabled:
            return

        for rule in self.rules:
            if rule.get("when") != event.type:
                continue

            if not self._rule_matches(rule, event):
                continue

            rule_id = rule.get("id", rule.get("when"))
            if not self._cooldown_ok(rule_id):
                continue

            self._execute_rule(rule, event)

    def _rule_matches(self, rule: dict[str, Any], event: PluginEvent) -> bool:
        conditions = rule.get("if") or rule.get("conditions") or []
        if isinstance(conditions, dict):
            if "all" in conditions:
                return all(self._condition_matches(item, event) for item in conditions.get("all", []))
            if "any" in conditions:
                return any(self._condition_matches(item, event) for item in conditions.get("any", []))
            conditions = [conditions]

        for condition in conditions:
            if not self._condition_matches(condition, event):
                return False

        return True

    def _condition_matches(self, condition: dict[str, Any], event: PluginEvent) -> bool:
        path = condition.get("path")
        op = condition.get("op", "eq")
        expected = condition.get("value")
        actual = self._get_value(event, path)
        return self._evaluate_condition(actual, op, expected)

    def _get_value(self, event: PluginEvent, path: str | None):
        if not path:
            return None

        if path == "event.type":
            return event.type
        if path == "event.source":
            return event.source
        if path == "event.severity":
            return event.severity

        if path.startswith("payload."):
            current = event.payload
            parts = path.split(".")[1:]
            for part in parts:
                if not isinstance(current, dict):
                    return None
                current = current.get(part)
            return current

        return None

    def _evaluate_condition(self, actual, op: str, expected) -> bool:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "in":
            return actual in (expected or [])
        if op == "contains":
            return expected in (actual or [])
        if op == "exists":
            return actual is not None
        if op == "not_exists":
            return actual is None
        if op == "truthy":
            return bool(actual)
        if op == "falsy":
            return not bool(actual)
        return False

    def _execute_rule(self, rule, event: PluginEvent):
        actions = self._normalize_actions(rule)
        rule_id = rule.get("id", rule.get("when", "rule"))
        results = []

        for action in actions:
            action_type = action.get("type")
            handler = self.actions.get(action_type)
            if not handler:
                results.append({"type": action_type, "error": "unknown action"})
                continue

            if self.dry_run:
                self.context.logger.info(
                    "[DRY RUN] Rule %s would execute action %s for event %s",
                    rule_id,
                    action_type,
                    event.type,
                )
                results.append({"type": action_type, "status": "dry_run"})
                continue

            try:
                result = handler(action, event)
                results.append({"type": action_type, **(result or {})})
            except Exception as exc:
                results.append({"type": action_type, "error": str(exc)})

        history_item = {
            "rule": rule_id,
            "event": event.type,
            "results": results,
        }
        self.execution_history.append(history_item)
        self.execution_history = self.execution_history[-100:]

        if any("error" in r for r in results):
            self.set_degraded("Rule execution failed", rule=rule_id, results=results)
        else:
            self.set_healthy("Rule executed", rule=rule_id, results=results)

    def _normalize_actions(self, rule: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(rule.get("actions"), list):
            return rule["actions"]

        then_value = rule.get("then")
        if isinstance(then_value, list):
            normalized = []
            for item in then_value:
                if isinstance(item, str):
                    normalized.append({"type": item})
                elif isinstance(item, dict):
                    normalized.append(item)
            return normalized

        if isinstance(then_value, str):
            action = {"type": then_value}
            for key in ("url", "command", "event", "payload"):
                if key in rule:
                    action[key] = rule[key]
            return [action]

        return []

    def _action_webhook(self, action: dict[str, Any], event: PluginEvent):
        url = action.get("url")
        if not url:
            raise ValueError("webhook action missing url")

        payload = action.get("payload") or {
            "event": event.type,
            "source": event.source,
            "severity": event.severity,
            "data": event.payload,
        }

        self.context.require_permission("network.outbound")
        response = requests.post(url, json=payload, timeout=3)
        response.raise_for_status()
        return {"status": response.status_code}

    def _action_command(self, action: dict[str, Any], event: PluginEvent):
        command = action.get("command")
        if not command:
            raise ValueError("command action missing command")

        self.context.require_permission("system.exec")
        subprocess.Popen(command, shell=True)
        return {"status": "started"}

    def _action_notify(self, action: dict[str, Any], event: PluginEvent):
        payload = action.get("payload") or {
            "event": event.type,
            "source": event.source,
            "severity": event.severity,
            "data": event.payload,
        }
        self.context.emit("automation.notify", payload)
        return {"status": "emitted", "event": "automation.notify"}

    def _action_emit(self, action: dict[str, Any], event: PluginEvent):
        event_name = action.get("event")
        if not event_name:
            raise ValueError("emit action missing event")

        payload = action.get("payload") or event.payload
        severity = action.get("severity", event.severity)
        self.context.emit(event_name, payload, severity=severity)
        return {"status": "emitted", "event": event_name}

    def stop(self):
        super().stop()
