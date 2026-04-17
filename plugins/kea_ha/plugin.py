from copy import deepcopy
import requests
from lib.plugin_api import DashboardPlugin, PluginEvent


class Plugin(DashboardPlugin):

    def setup(self, context):
        super().setup(context)

        self.previous_cluster_status = None
        self.config = context.get_plugin_config("kea_ha")
        self.nodes = self._load_nodes()

        context.register_route(
            "/api/plugins/kea-ha/status",
            self.get_status
        )

        context.register_dashboard_card(
            "kea_ha_status",
            "Kea HA Status",
            render=self.render_card,
            order=10
        )

        scheduler = context.get_service("scheduler")
        if scheduler:
            scheduler.every(
                "kea_ha_poll",
                self.config.get("poll_interval", 5),
                self.poll
            )

    def render_card(self):
        status = self.get_status()
        active = status.get("active_node")
        partner_down = status.get("partner_down_nodes", [])
        return f"<div><strong>Active:</strong> {active}<br/><strong>Partner Down:</strong> {partner_down}</div>"

    def _load_nodes(self):
        configured_nodes = self.config.get("nodes")
        if isinstance(configured_nodes, dict) and configured_nodes:
            return configured_nodes

        return {
            "kea1": "http://127.0.0.1:8000",
        }

    def poll(self):
        try:
            cluster_status = self.get_status()
            self.set_healthy("Polling OK", node_count=len(cluster_status.get("nodes", {})))
        except Exception as exc:
            self.set_degraded("Polling failed", error=str(exc))

    def _extract_ha_record(self, response_json):
        if isinstance(response_json, list) and response_json:
            response_json = response_json[0]

        arguments = response_json.get("arguments", {}) if isinstance(response_json, dict) else {}
        ha_list = arguments.get("high-availability", [])
        if not ha_list:
            return {}

        return ha_list[0] or {}

    def _normalize_node_status(self, node_name, response_json=None, error=None):
        if error:
            return {
                "node": node_name,
                "reachable": False,
                "error": error,
                "mode": None,
                "local_role": None,
                "local_state": None,
                "remote_role": None,
                "remote_state": None,
                "raw": None,
            }

        ha = self._extract_ha_record(response_json)
        local = ha.get("local", {})
        remote = ha.get("remote", {})

        return {
            "node": node_name,
            "reachable": True,
            "error": None,
            "mode": ha.get("ha-mode"),
            "local_role": local.get("role"),
            "local_state": local.get("state"),
            "remote_role": remote.get("role"),
            "remote_state": remote.get("state"),
            "raw": response_json,
        }

    def _get_active_node_name(self, cluster_status):
        for node_name, node_status in cluster_status.get("nodes", {}).items():
            if node_status.get("local_state") == "active":
                return node_name
        return None

    def _build_cluster_status(self, node_results):
        active_node = self._get_active_node_name({"nodes": node_results})
        partner_down_nodes = []

        for node_name, node_status in node_results.items():
            if node_status.get("local_state") == "partner-down":
                partner_down_nodes.append(node_name)
            if node_status.get("remote_state") == "partner-down":
                partner_down_nodes.append(node_name)

        return {
            "nodes": node_results,
            "active_node": active_node,
            "partner_down_nodes": sorted(set(partner_down_nodes)),
        }

    def _emit_events(self, cluster_status):
        previous = self.previous_cluster_status

        self.context.event_bus.emit(PluginEvent(
            type="kea.ha.status",
            source="kea_ha",
            payload=deepcopy(cluster_status)
        ))

        if previous is None:
            self.previous_cluster_status = deepcopy(cluster_status)
            return

        if previous != cluster_status:
            self.context.event_bus.emit(PluginEvent(
                type="kea.ha.state_changed",
                source="kea_ha",
                payload={
                    "previous": deepcopy(previous),
                    "current": deepcopy(cluster_status),
                }
            ))

        previous_active = previous.get("active_node")
        current_active = cluster_status.get("active_node")
        if previous_active != current_active:
            self.context.event_bus.emit(PluginEvent(
                type="kea.ha.failover_detected",
                source="kea_ha",
                payload={
                    "from": previous_active,
                    "to": current_active,
                    "previous": deepcopy(previous),
                    "current": deepcopy(cluster_status),
                }
            ))

        previous_partner_down = set(previous.get("partner_down_nodes", []))
        current_partner_down = set(cluster_status.get("partner_down_nodes", []))
        if current_partner_down and current_partner_down != previous_partner_down:
            self.context.event_bus.emit(PluginEvent(
                type="kea.ha.partner_down",
                source="kea_ha",
                payload={
                    "nodes": sorted(current_partner_down),
                    "previous": deepcopy(previous),
                    "current": deepcopy(cluster_status),
                }
            ))

        self.previous_cluster_status = deepcopy(cluster_status)

    def get_status(self, handler=None):
        node_results = {}

        for name, url in self.nodes.items():
            try:
                response = requests.post(
                    url,
                    json={
                        "command": "ha-status",
                        "service": ["dhcp4"],
                    },
                    timeout=2,
                )
                response.raise_for_status()
                node_results[name] = self._normalize_node_status(
                    name,
                    response_json=response.json(),
                )
            except Exception as exc:
                node_results[name] = self._normalize_node_status(
                    name,
                    error=str(exc),
                )

        cluster_status = self._build_cluster_status(node_results)
        self._emit_events(cluster_status)
        return cluster_status

    def stop(self):
        scheduler = self.context.get_service("scheduler")
        if scheduler:
            scheduler.cancel("kea_ha_poll")
        super().stop()
