import time
import subprocess
import requests
from lib.plugin_api import DashboardPlugin, PluginEvent


class Plugin(DashboardPlugin):

    def setup(self, context):
        super().setup(context)

        cfg = context.get_plugin_config("automation")

        self.enabled = bool(cfg.get("enabled", context.config.get("automation_enabled", False)))
        self.dry_run = bool(cfg.get("dry_run", context.config.get("automation_dry_run", True)))
        self.cooldown = int(cfg.get("cooldown", context.config.get("automation_cooldown", 60)))
        self.rules = cfg.get("rules", [])

        self.last_run = {}

        # Subscribe dynamically based on rules
        for rule in self.rules:
            event_type = rule.get("when")
            if event_type:
                context.subscribe(event_type, self._handle_event)

        self.set_healthy("Automation ready", rules=len(self.rules))

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

            rule_id = rule.get("id", rule.get("when"))

            if not self._cooldown_ok(rule_id):
                continue

            self._execute_rule(rule, event)

    def _execute_rule(self, rule, event: PluginEvent):
        action = rule.get("then")
        payload = {
            "event": event.type,
            "data": event.payload
        }

        if self.dry_run:
            self.context.logger.info(f"[DRY RUN] Rule {rule.get('id')} would execute {action} with {payload}")
            return

        try:
            if action == "webhook":
                url = rule.get("url")
                if url:
                    requests.post(url, json=payload, timeout=3)

            elif action == "command":
                cmd = rule.get("command")
                if cmd:
                    subprocess.Popen(cmd, shell=True)

            elif action == "notify":
                # delegate to HA plugin via event
                self.context.emit("automation.notify", payload)

            self.set_healthy("Rule executed", rule=rule.get("id"))

        except Exception as exc:
            self.set_degraded("Rule execution failed", error=str(exc), rule=rule.get("id"))

    def stop(self):
        super().stop()
