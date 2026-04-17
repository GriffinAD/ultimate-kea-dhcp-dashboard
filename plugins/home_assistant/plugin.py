from datetime import datetime, timezone
from lib.plugin_system import DashboardPlugin
import requests


class Plugin(DashboardPlugin):
    def register(self, context):
        self.context = context
        self.webhook_url = context.config.get("home_assistant_webhook")
        self.send_status_events = bool(context.config.get("home_assistant_send_status_events", False))
        self.last_sent_signatures = {}

        context.register_route(
            "/api/plugins/home-assistant/test",
            self.send_test
        )
        context.register_route(
            "/api/plugins/home-assistant/status",
            self.get_status
        )

        if self.send_status_events:
            context.event_bus.subscribe("kea.ha.status", self.handle_ha_status)
        context.event_bus.subscribe("kea.ha.state_changed", self.handle_state_changed)
        context.event_bus.subscribe("kea.ha.failover_detected", self.handle_failover)
        context.event_bus.subscribe("kea.ha.partner_down", self.handle_partner_down)

    def send_test(self, handler=None):
        payload = self._build_payload(
            event_name="test",
            severity="info",
            title="Home Assistant plugin test",
            message="Home Assistant plugin test successful",
            data={},
        )
        return self._send(payload, dedupe=False)

    def get_status(self, handler=None):
        return {
            "configured": bool(self.webhook_url),
            "send_status_events": self.send_status_events,
            "dedupe_cache_size": len(self.last_sent_signatures),
        }

    def handle_ha_status(self, data):
        active_node = data.get("active_node")
        payload = self._build_payload(
            event_name="kea_ha_status",
            severity="info",
            title="Kea HA status",
            message=f"Cluster active node: {active_node}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def handle_state_changed(self, data):
        current = data.get("current", {})
        active_node = current.get("active_node")
        payload = self._build_payload(
            event_name="kea_ha_state_changed",
            severity="warning",
            title="Kea HA state changed",
            message=f"Cluster state changed. Active node: {active_node}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def handle_failover(self, data):
        payload = self._build_payload(
            event_name="kea_failover",
            severity="critical",
            title="Kea HA failover detected",
            message=f"Failover detected: {data.get('from')} -> {data.get('to')}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def handle_partner_down(self, data):
        nodes = ", ".join(data.get("nodes", [])) or "unknown"
        payload = self._build_payload(
            event_name="kea_partner_down",
            severity="critical",
            title="Kea HA partner down",
            message=f"Partner down detected on nodes: {nodes}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def _build_payload(self, event_name, severity, title, message, data):
        return {
            "event": event_name,
            "severity": severity,
            "title": title,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

    def _signature_for_payload(self, payload):
        event_name = payload.get("event")
        data = payload.get("data", {})
        if event_name == "kea_failover":
            return f"{event_name}:{data.get('from')}:{data.get('to')}"
        if event_name == "kea_partner_down":
            nodes = ",".join(sorted(data.get("nodes", [])))
            return f"{event_name}:{nodes}"
        if event_name == "kea_ha_state_changed":
            current = data.get("current", {})
            return f"{event_name}:{current.get('active_node')}:{','.join(current.get('partner_down_nodes', []))}"
        if event_name == "kea_ha_status":
            cluster = payload.get("data", {})
            return f"{event_name}:{cluster.get('active_node')}:{','.join(cluster.get('partner_down_nodes', []))}"
        return payload.get("event", "unknown")

    def _send(self, payload, dedupe=True):
        if not self.webhook_url:
            return {"error": "No webhook configured", "payload": payload}

        signature = self._signature_for_payload(payload)
        if dedupe and self.last_sent_signatures.get(payload.get("event")) == signature:
            return {"status": "deduped", "signature": signature}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=3)
            response.raise_for_status()
            self.last_sent_signatures[payload.get("event")] = signature
            return {"status": response.status_code, "signature": signature}
        except Exception as exc:
            return {"error": str(exc), "payload": payload}

    def start(self):
        pass

    def stop(self):
        pass
