import time
import subprocess
import requests
from lib.plugin_system import DashboardPlugin


class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.last_run = {}

        cfg = context.config
        self.enabled = bool(cfg.get("automation_enabled", False))
        self.dry_run = bool(cfg.get("automation_dry_run", True))
        self.cooldown = int(cfg.get("automation_cooldown", 60))
        self.webhook = cfg.get("automation_webhook")
        self.command = cfg.get("automation_command")

        context.event_bus.subscribe("kea.ha.failover_detected", self.handle_failover)
        context.event_bus.subscribe("kea.ha.partner_down", self.handle_partner_down)

    def _cooldown_ok(self, key):
        now = time.time()
        last = self.last_run.get(key, 0)
        if now - last < self.cooldown:
            return False
        self.last_run[key] = now
        return True

    def handle_failover(self, data):
        if not self.enabled:
            return
        if not self._cooldown_ok("failover"):
            return
        self._execute("failover", data)

    def handle_partner_down(self, data):
        if not self.enabled:
            return
        if not self._cooldown_ok("partner_down"):
            return
        self._execute("partner_down", data)

    def _execute(self, event_type, data):
        payload = {
            "event": event_type,
            "data": data
        }

        if self.dry_run:
            self.context.logger.info(f"[DRY RUN] Would execute automation: {payload}")
            return

        if self.webhook:
            try:
                requests.post(self.webhook, json=payload, timeout=3)
            except Exception as e:
                self.context.logger.warning(f"Webhook failed: {e}")

        if self.command:
            try:
                subprocess.Popen(self.command, shell=True)
            except Exception as e:
                self.context.logger.warning(f"Command failed: {e}")

    def start(self):
        pass

    def stop(self):
        pass
