from __future__ import annotations

import json
import logging
import runpy
import threading
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_system import PluginManager
from core.plugin_health import PluginHealth
from server.alerts import Alerts


LOGGER = logging.getLogger("ukd.plugin_runtime")


class PluginRuntime:
    def __init__(self, script_path: Path) -> None:
        self.script_path = Path(script_path)
        self.namespace = runpy.run_path(str(self.script_path), run_name="ukd_base")
        self.root_dir = self.script_path.parent.parent
        self.plugin_manager = None

    def _render_plugin_cards_html(self) -> str:
        if not self.plugin_manager:
            return ""

        html_parts = []
        for card in self.plugin_manager.get_dashboard_cards():
            try:
                content = card.render() if card.render else ""
            except Exception as exc:
                LOGGER.warning("Failed to render card %s: %s", card.id, exc)
                continue

            html_parts.append(
                f"""
                <div class=\"info plugin-card\">\n"
                f"                    <h2>{card.title}</h2>\n"
                f"                    <div class=\"plugin-card-body\">{content}</div>\n"
                f"                </div>\n"
                """
            )

        return "\n".join(html_parts)

    def _patch_generate_html(self) -> None:
        original_generate_html = self.namespace["generate_html"]
        runtime = self

        def patched_generate_html(info, lang="fr"):
            html = original_generate_html(info, lang)
            cards_html = runtime._render_plugin_cards_html()
            marker = "\n            <h2>{t['dhcp_pools']}"
            replacement = f"\n            {cards_html}\n            <h2{{t['dhcp_pools']}}"
            if cards_html and marker in html:
                html = html.replace(marker, replacement, 1)
            return html

        self.namespace["generate_html"] = patched_generate_html

    def _dispatch_plugin_route(self, handler, parsed_path: str, method: str) -> bool:
        if not self.plugin_manager:
            return False

        for route in self.plugin_manager.get_registered_routes():
            if parsed_path != route.path:
                continue
            if method not in [m.upper() for m in route.methods]:
                continue

            try:
                result = route.handler(handler)
                self.plugin_manager.health.set(route.plugin_id, "healthy")
            except TypeError:
                result = route.handler()
                self.plugin_manager.health.set(route.plugin_id, "healthy")
            except Exception as exc:
                LOGGER.exception("Plugin route failed for %s", route.path)
                self.plugin_manager.health.set(route.plugin_id, "unhealthy", str(exc))
                self.plugin_manager.alerts.push("critical", f"{route.plugin_id} failed", route.plugin_id)
                handler.send_response(500)
                handler.send_header("Content-type", "application/json; charset=utf-8")
                handler.end_headers()
                handler.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
                return True

            if isinstance(result, dict) and result.get("_plugin_handled"):
                return True

            if isinstance(result, str):
                content_type = "text/plain; charset=utf-8"
                payload = result.encode("utf-8")
            else:
                content_type = "application/json; charset=utf-8"
                payload = json.dumps(result).encode("utf-8")

            handler.send_response(200)
            handler.send_header("Content-type", content_type)
            handler.send_header("Cache-Control", "no-cache")
            handler.end_headers()
            handler.wfile.write(payload)
            return True

        return False

    def _patch_handler(self) -> None:
        original_handler_class = self.namespace["KeaHandler"]
        original_do_get = original_handler_class.do_GET
        runtime = self

        def patched_do_get(self):
            parsed = urlparse(self.path)
            if runtime._dispatch_plugin_route(self, parsed.path, "GET"):
                return
            return original_do_get(self)

        def patched_do_post(self):
            parsed = urlparse(self.path)
            if runtime._dispatch_plugin_route(self, parsed.path, "POST"):
                return
            self.send_response(404)
            self.end_headers()

        original_handler_class.do_GET = patched_do_get
        original_handler_class.do_POST = patched_do_post
        self.namespace["KeaHandler"] = original_handler_class

    def initialize_plugins(self) -> None:
        config = self.namespace["config"]
        self.plugin_manager = PluginManager(root_dir=self.root_dir, config=config)
        self.plugin_manager.discover()
        self.plugin_manager.load_enabled_plugins()
        self.plugin_manager.context.register_service("plugin_manager", self.plugin_manager)

        # NEW: attach health + alerts
        self.plugin_manager.health = PluginHealth()
        self.plugin_manager.alerts = Alerts()

        self.plugin_manager.start_all()
        self.namespace["plugin_manager"] = self.plugin_manager

    def start(self) -> None:
        load_config = self.namespace["load_config"]
        run_server = self.namespace["run_server"]

        load_config()
        self.initialize_plugins()
        self._patch_generate_html()
        self._patch_handler()

        cache_thread = threading.Thread(target=self.namespace["update_dhcp_cache"], daemon=True)
        cache_thread.start()

        config = self.namespace["config"]
        if config.get("enable_scanner"):
            scan_thread = threading.Thread(target=self.namespace["network_scanner_thread"], daemon=True)
            scan_thread.start()
            self.namespace["SCAN_THREAD"] = scan_thread

        try:
            run_server()
        finally:
            if self.plugin_manager:
                self.plugin_manager.stop_all()
