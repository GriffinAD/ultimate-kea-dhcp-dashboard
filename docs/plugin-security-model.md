
# Plugin Security Model

Permissions are declared in plugin manifests and enforced by:
1. manifest validation
2. trust-level validation
3. policy engine checks
4. runtime permission checks
5. audit logging

Sensitive permissions:
- network.outbound
- system.exec
- plugin.control
- plugin.install
- kea.write
- kea.ha.control
