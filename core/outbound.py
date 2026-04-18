
from __future__ import annotations

from urllib.parse import urlparse
import requests


class OutboundClient:
    def __init__(self, context):
        self.context = context

    def post_json(self, plugin_id: str, url: str, payload: dict, timeout: int = 3):
        self.context.require_permission("network.outbound")
        host = urlparse(url).hostname or ""
        if not self.context.security.policy.is_host_allowed(plugin_id, host):
            self.context.audit.log(
                plugin=plugin_id,
                permission="network.outbound",
                action="http.post",
                target=url,
                status="denied",
                details={"reason": "host not allowed"},
            )
            raise PermissionError(f"{plugin_id} outbound host blocked by policy: {host}")

        response = requests.post(url, json=payload, timeout=timeout)
        self.context.audit.log(
            plugin=plugin_id,
            permission="network.outbound",
            action="http.post",
            target=url,
            status="allowed" if response.ok else "failed",
            details={"status_code": response.status_code},
        )
        response.raise_for_status()
        return response
