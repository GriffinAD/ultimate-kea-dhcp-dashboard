from datetime import datetime, timezone
import time

import requestsfrom core.outbound import OutboundClient
from core.plugin_api import DashboardPlugin, PluginEvent


class Plugin(DashboardPlugin):
    def setup(self, context):
        super().setup(context)

        cfg = context.get_plugin_config("home_assistant")

        self.webhook_url = cfg.get("webhook") or cfg.get("url") or context.config.get("home_assistant_webhook")
        self.send_status_events = bool(
            cfg.get("send_status_events", context.config.get("home_assistant_send_status_events", False))
        )
        self.retry_count = int(cfg.get("retry_count", context.config.get("home_assistant_retry_count", 3)))
        self.retry_backoff_seconds = float(
            cfg.get("retry_backoff_seconds", context.config.get("home_assistant_retry_backoff_seconds", 1.5))
        )
        self.routing = cfg.get(
            "routing",
            context.config.get(
                "home_assistant_routing",
                {
                    "critical": self.webhook_url,
                    "warning": self.webhook_url,
                    "info": self.webhook_url,
                },
            ),
        )
        self.last_sent_signatures = {}
        self.delivery_failures = {}

        context.register_route(
            "/api/plugins/home_assistant/test",
            self.send_test
        )
        context.register_route(
            "/api/plugins/home_assistant/status",
            self.get_status
        )

        if self.send_status_events:
            context.subscribe("kea.ha.status", self.handle_ha_status)
        context.subscribe("kea.ha.state_changed", self.handle_state_changed)
        context.subscribe("kea.ha.failover_detected", self.handle_failover)
        context.subscribe("kea.ha.partner_down", self.handle_partner_down)

        self.set_healthy("Configured", configured=bool(self.webhook_url))

    def send_test(self, handler=None):
        payload = self._build_payload(
            event_name="test",
            severity="info",
            title="Home Assistant plugin test",
            message="Home Assistant plugin test successful",
            data={},
        )
        result = self._send(payload, dedupe=False)
        if "error" in result:
            self.set_degraded("Test delivery failed", error=result.get("error"))
        else:
            self.set_healthy("Test delivery OK")
        return result

    def get_status(self, handler=None):
        return {
            "configured": bool(self.webhook_url),
            "send_status_events": self.send_status_events,
            "dedupe_cache_size": len(self.last_sent_signatures),
            "routing": self.routing,
            "retry_count": self.retry_count,
            "delivery_failures": self.delivery_failures,
            "health": self.health().__dict__,
        }

    def handle_ha_status(self, event: PluginEvent):
        data = event.payload
        active_node = data.get("active_node")
        payload = self._build_payload(
            event_name="kea_ha_status",
            severity="info",
            title="Kea HA status",
            message=f"Cluster active node: {active_node}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def handle_state_changed(self, event: PluginEvent):
        data = event.payload
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

    def handle_failover(self, event: PluginEvent):
        data = event.payload
        payload = self._build_payload(
            event_name="kea_failover",
            severity="critical",
            title="Kea HA failover detected",
            message=f"Failover detected: {data.get('from')} -> {data.get('to')}",
            data=data,
        )
        self._send(payload, dedupe=True)

    def handle_partner_down(self, event: PluginEvent):
        data = event.payload
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

    def _resolve_destination(self, severity):
        destination = self.routing.get(severity)
        if destination == "ignore":
            return None
        return destination or self.webhook_url

    def _send_with_retry(self, destination, payload):
        last_error = None
        for attempt in range(1, self.retry_count + 1):
            try:
                self.context.require_permission("network.outbound")
                response = self.outbound.post_json(self.manifest.id, destination, json=payload, timeout=3)
                response.raise_for_status()
                return {
                    "status": response.status_code,
                    "attempts": attempt,
                    "destination": destination,
                }
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.retry_count:
                    time.sleep(self.retry_backoff_seconds * attempt)
        return {
            "error": last_error or "unknown delivery error",
            "attempts": self.retry_count,
            "destination": destination,
        }

    def _send(self, payload, dedupe=True):
        destination = self._resolve_destination(payload.get("severity", "info"))
        if not destination:
            return {"status": "ignored", "reason": "routing", "payload": payload}

        signature = self._signature_for_payload(payload)
        event_name = payload.get("event")
        if dedupe and self.last_sent_signatures.get(event_name) == signature:
            return {"status": "deduped", "signature": signature}

        result = self._send_with_retry(destination, payload)
        if "error" in result:
            self.delivery_failures[event_name] = result
            self.set_degraded("Delivery failed", error=result.get("error"), event=event_name)
            return {**result, "payload": payload}

        self.last_sent_signatures[event_name] = signature
        self.delivery_failures.pop(event_name, None)
        self.set_healthy("Delivery OK", event=event_name)
        return {**result, "signature": signature}

    def stop(self):
        super().stop()
