# Contributing to Ultimate DHCP Dashboard

## Code Organization

The project follows a modular architecture with strict boundaries between layers:

- `bin/` - Executable entry points
  - `bin/ultimate-kea-dashboard` - Main application and HTTP server
  - `bin/ultimate-kea-dashboard-plugin` - Plugin runtime entry point
- `core/` - Platform and plugin runtime
  - `core/plugin_api.py` - Plugin contract (events, manifests, protocols, base class)
  - `core/plugin_system.py` - Plugin manager
  - `core/plugin_runtime.py` - Plugin runtime bootstrapper
  - `core/plugin_health.py` - Plugin health tracking
  - `core/event_bus.py` - Event bus implementation
  - `core/marketplace.py` / `core/security.py` - Marketplace + trust model
  - `core/registry/` - Plugin registry JSONs (installed, available, trusted)
- `server/` - Built-in backend services
  - `server/config.py` - Configuration loading
  - `server/stats.py` - System statistics collection
  - `server/scheduler.py` / `server/alerts.py` / `server/update_checker.py`
  - `server/utils.py`
  - `server/discovery/` - Network and device discovery
    - `network_scanner.py`, `device_detection.py`, `mac_vendor.py`, `custom_devices.py`
- `plugins/` - Optional feature plugins (each with its own `manifest.json`)
- `ui/` - Frontend code served to the browser
  - `ui/themes/theme_registry.py` - Theme definitions
  - `ui/i18n/translations.py` - Translation loader
  - `ui/components/` - Client-side JavaScript components (e.g. `gauges.js`)
  - `ui/shell/`, `ui/pages/`, `ui/plugins/`
- `assets/` - Passive static files (icons, images, fonts, css)
- `data/` - Runtime data (e.g. `translations.json`)
- `etc/` - Configuration files, systemd unit, example configs
- `docs/` - User and developer documentation
- `packaging/` - Debian/RPM/Arch/Docker packaging
- `tests/` - Unit, integration, UI and packaging tests

### Ownership rules

- `core/` owns platform and plugin runtime concerns.
- `server/` owns built-in backend concerns.
- `plugins/` owns optional feature packages.
- `ui/` owns frontend source and browser logic.
- `assets/` owns passive files only.

### Import conventions

- Fully-qualified imports only: `from server.stats import ...`, `from core.plugin_api import ...`, `from ui.i18n.translations import ...`.
- Scripts in `bin/` add the repo root to `sys.path` and then import via the package paths above.
- Browser-facing paths use `/ui/...` for app code and `/assets/...` for passive files. `/static/` is no longer served.

## Development Setup

1. Clone the repository
2. Copy `etc/ultimate-dashboard.conf.example` to `etc/ultimate-kea-dashboard.conf`
3. Configure your environment-specific settings
4. Install dependencies: `pip3 install -r requirements.txt`

## Code Style

- Follow PEP 8 guidelines for Python code
- Use descriptive function and variable names
- Add docstrings to all public functions
- Keep functions focused and modular
- Avoid hardcoded credentials or paths
- Prefer package-qualified imports; avoid relying on `sys.path` hacks

## Security Best Practices

- Never commit sensitive data (passwords, tokens, certificates)
- Use placeholder values in example configurations
- Sanitize user inputs before processing
- Follow principle of least privilege for file permissions

## Testing Changes

Before submitting changes:

1. Syntax check entry points and packages:
   ```bash
   python3 -m py_compile bin/ultimate-kea-dashboard bin/ultimate-kea-dashboard-plugin
   python3 -m compileall core server ui plugins
   ```
2. Smoke-test imports from the repo root:
   ```bash
   PYTHONPATH=. python3 -c "import core, server, server.discovery, ui.themes.theme_registry, ui.i18n.translations"
   ```
3. Verify configuration loading works correctly
4. Run the dashboard locally and check `/`, `/api/stats`, `/ui/...`, `/assets/icons/...`
5. Check for memory leaks in long-running processes

## Pull Request Guidelines

- Provide a clear description of changes
- Reference any related issues
- Ensure code passes syntax checks
- Update documentation (and this file) if you change the layout
- Test on a target environment before submitting

## Reporting Issues

When reporting bugs, include:
- Operating system and Python version
- ISC Kea DHCP version
- Complete error messages and stack traces
- Steps to reproduce the issue
- Configuration details (sanitized)
