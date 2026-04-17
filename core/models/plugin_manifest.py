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
