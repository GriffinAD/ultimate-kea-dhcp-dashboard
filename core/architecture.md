# Target Architecture (PR Phases Alignment)

## Core App

- Router (HTTP + plugin routing bridge)
- Plugin Manager (lifecycle, DI, discovery)
- Marketplace (install/update/remove plugins) [NOT IMPLEMENTED]
- Security Layer (capabilities, permissions, sandboxing) [NOT IMPLEMENTED]
- UI Shell (SPA host + plugin UI loader) [PARTIAL]

## Plugins

- kea_ha (existing)
- home_assistant (existing)
- prometheus (planned)
- automation (PARTIAL - rules + webhook)
- admin (PARTIAL - health/alerts, missing control plane)

## Gap Summary

### Missing Core
- Marketplace
- Security layer (permissions, capability flags)
- Proper UI shell (SPA router, plugin UI sandbox)

### Missing Plugin Maturity
- automation: needs conditions, UI, more actions
- admin: needs plugin management UI + controls
- home_assistant: needs proper integration hooks
- prometheus: not implemented

## Next Steps (Production Alignment)

1. Build UI Shell (true SPA + plugin UI mounting)
2. Add Security Layer (plugin capability flags)
3. Implement Marketplace (basic local registry first)
4. Complete Admin Control Plane
5. Expand Automation Engine (conditions + UI)

---

This document reflects the *actual* state vs the intended PR phases discussed.
