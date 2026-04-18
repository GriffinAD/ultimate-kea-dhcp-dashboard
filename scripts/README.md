# scripts/

One-off development and automation scripts. These are **not** runtime
components of the dashboard and must not be shipped with packages.

They are kept in the repo as an audit trail of the large code-generation
passes that produced the current plugin/capability architecture.

## Contents

- `apply_capability_model_plugin.sh` — bulk generator that wrote the
  initial `core/models`, `core/contracts`, the capability/permission
  security model, and the `admin` plugin scaffold. Safe to re-run only
  on a branch named `plugin`; it overwrites generated files.
- `final_hardening_pass.sh` — follow-up hardening pass applied on top
  of the capability model (validation, audit, outbound policy, etc.).

## Usage

Run from the repository root:

```bash
./scripts/apply_capability_model_plugin.sh .
./scripts/final_hardening_pass.sh .
```

Both scripts assume a clean working tree and expect to be run on a
dedicated branch. Review the resulting diff before committing.
