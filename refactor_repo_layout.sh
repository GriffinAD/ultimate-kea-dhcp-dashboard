#!/usr/bin/env bash
set -Eeuo pipefail

# Refactor script for ultimate-kea-dhcp-dashboard
# Safe-ish local migration from plugin branch layout toward:
# core/ server/ plugins/ ui/ assets/
#
# What it does automatically:
# - verifies repo + branch + clean working tree
# - scaffolds target directories
# - moves plugin platform files lib/ -> core/
# - moves backend files lib/ -> server/
# - moves theme/i18n files lib/ -> ui/
# - moves registry JSONs into core/registry/
# - moves static/icons -> assets/icons
# - updates imports and known path references
# - optionally deletes lib/ if empty
#
# What it does NOT fully automate:
# - classification of static/js application logic vs passive vendor assets
#   It leaves static/js in place and prints a follow-up checklist.
#
# Usage:
#   ./refactor_repo_layout.sh            # execute
#   ./refactor_repo_layout.sh --dry-run  # show plan only
#   ./refactor_repo_layout.sh --force    # allow dirty working tree

DRY_RUN=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
run() {
  if (( DRY_RUN )); then
    printf 'DRY-RUN: %q' "$1"
    shift || true
    for x in "$@"; do printf ' %q' "$x"; done
    printf '\n'
  else
    "$@"
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

require_cmd git
require_cmd python3

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [[ -z "$ROOT" ]]; then
  echo "Not inside a git repository." >&2
  exit 1
fi
cd "$ROOT"

REPO_NAME=$(basename "$ROOT")
if [[ "$REPO_NAME" != "ultimate-kea-dhcp-dashboard" ]]; then
  echo "Expected repo directory name 'ultimate-kea-dhcp-dashboard', got '$REPO_NAME'." >&2
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "refactor" ]]; then
  echo "Current branch is '$CURRENT_BRANCH'. Switch to 'refactor' first." >&2
  exit 1
fi

if (( ! FORCE )); then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is not clean. Commit/stash first, or rerun with --force." >&2
    exit 1
  fi
fi

say "Creating target directories"
DIRS=(
  core/contracts
  core/models
  core/registry
  server/discovery
  server/kea
  server/api
  server/metrics
  server/services
  ui/shell
  ui/pages
  ui/components
  ui/plugins
  ui/themes
  ui/i18n
  assets/icons
  assets/images
  assets/fonts
  assets/css
  tests/unit
  tests/integration
  tests/ui
  tests/packaging
)
for d in "${DIRS[@]}"; do
  run mkdir -p "$d"
done

say "Moving platform files from lib/ to core/"
move_if_exists() {
  local src="$1" dst="$2"
  if [[ -e "$src" && ! -e "$dst" ]]; then
    run git mv "$src" "$dst"
  fi
}

move_if_exists lib/event_bus.py core/event_bus.py
move_if_exists lib/plugin_api.py core/plugin_api.py
move_if_exists lib/plugin_health.py core/plugin_health.py
move_if_exists lib/plugin_runtime.py core/plugin_runtime.py
move_if_exists lib/plugin_system.py core/plugin_system.py

say "Moving backend files from lib/ to server/"
move_if_exists lib/alerts.py server/alerts.py
move_if_exists lib/config.py server/config.py
move_if_exists lib/scheduler.py server/scheduler.py
move_if_exists lib/stats.py server/stats.py
move_if_exists lib/update_checker.py server/update_checker.py
move_if_exists lib/utils.py server/utils.py
move_if_exists lib/custom_devices.py server/discovery/custom_devices.py
move_if_exists lib/device_detection.py server/discovery/device_detection.py
move_if_exists lib/mac_vendor.py server/discovery/mac_vendor.py
move_if_exists lib/network_scanner.py server/discovery/network_scanner.py

say "Moving UI-adjacent files from lib/ to ui/"
move_if_exists lib/themes.py ui/themes/theme_registry.py
move_if_exists lib/translations.py ui/i18n/translations.py

say "Moving core registry files"
move_if_exists core/installed_plugins.json core/registry/installed_plugins.json
move_if_exists core/plugin_registry.json core/registry/plugin_registry.json
move_if_exists core/trusted_plugins.json core/registry/trusted_plugins.json

say "Moving passive assets"
if [[ -d static/icons ]]; then
  # merge safely if assets/icons already exists
  if (( DRY_RUN )); then
    echo "DRY-RUN: move contents static/icons -> assets/icons"
  else
    shopt -s dotglob nullglob
    for f in static/icons/*; do
      git mv "$f" assets/icons/ 2>/dev/null || mv "$f" assets/icons/
    done
    shopt -u dotglob nullglob
    rmdir static/icons 2>/dev/null || true
  fi
fi

say "Updating imports and known path references"
if (( DRY_RUN )); then
  echo "DRY-RUN: would run Python rewrite step"
else
python3 <<'PY'
from pathlib import Path

root = Path('.')

replacements = [
    # lib.* -> core.* (platform/plugin runtime)
    ('from lib.plugin_api import', 'from core.plugin_api import'),
    ('from lib.event_bus import', 'from core.event_bus import'),
    ('from lib.plugin_health import', 'from core.plugin_health import'),
    ('from lib.plugin_runtime import', 'from core.plugin_runtime import'),
    ('from lib.plugin_system import', 'from core.plugin_system import'),
    ('import lib.plugin_api', 'import core.plugin_api'),
    ('import lib.event_bus', 'import core.event_bus'),
    ('import lib.plugin_health', 'import core.plugin_health'),
    ('import lib.plugin_runtime', 'import core.plugin_runtime'),
    ('import lib.plugin_system', 'import core.plugin_system'),

    # lib.* -> server.* (backend)
    ('from lib.alerts import', 'from server.alerts import'),
    ('from lib.config import', 'from server.config import'),
    ('from lib.scheduler import', 'from server.scheduler import'),
    ('from lib.stats import', 'from server.stats import'),
    ('from lib.update_checker import', 'from server.update_checker import'),
    ('from lib.utils import', 'from server.utils import'),

    # lib.* -> server.discovery.* (network/device discovery)
    ('from lib.custom_devices import', 'from server.discovery.custom_devices import'),
    ('from lib.device_detection import', 'from server.discovery.device_detection import'),
    ('from lib.mac_vendor import', 'from server.discovery.mac_vendor import'),
    ('from lib.network_scanner import', 'from server.discovery.network_scanner import'),

    # lib.* -> ui.*
    ('from lib.themes import', 'from ui.themes.theme_registry import'),
    ('from lib.translations import', 'from ui.i18n.translations import'),

    # Bare imports that used to rely on sys.path.insert(lib/)
    ('from themes import', 'from ui.themes.theme_registry import'),
    ('from translations import', 'from ui.i18n.translations import'),
    ('from stats import', 'from server.stats import'),
    ('from alerts import', 'from server.alerts import'),
    ('from config import', 'from server.config import'),
    ('from scheduler import', 'from server.scheduler import'),
    ('from update_checker import', 'from server.update_checker import'),
    ('from utils import', 'from server.utils import'),
    ('from network_scanner import', 'from server.discovery.network_scanner import'),
    ('from device_detection import', 'from server.discovery.device_detection import'),
    ('from mac_vendor import', 'from server.discovery.mac_vendor import'),
    ('import custom_devices', 'from server.discovery import custom_devices'),

    # Path/URL rewrites
    ('/static/icons/', '/assets/icons/'),
    ('"static/icons/', '"assets/icons/'),
    ("'static/icons/", "'assets/icons/"),
    ('/static/js/gauges.js', '/ui/components/gauges.js'),
]

suffixes = {'.py', '.sh', '.md', '.js', '.html', '.json', '.service'}
changed = []
for path in root.rglob('*'):
    if not path.is_file() or path.suffix not in suffixes:
        continue
    # Skip git internals and generated data
    if '.git/' in path.as_posix():
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        continue
    original = text
    for a, b in replacements:
        text = text.replace(a, b)
    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append(path.as_posix())

print('Rewritten files:')
for p in changed:
    print(' -', p)
PY
fi

say "Normalising plugin manifests (optional minimal standardisation)"
if (( ! DRY_RUN )); then
python3 <<'PY'
from pathlib import Path
import json

plugins_dir = Path('plugins')
for manifest in plugins_dir.glob('*/manifest.json'):
    data = json.loads(manifest.read_text(encoding='utf-8'))
    plugin_dir = manifest.parent
    backend_dir = plugin_dir / 'backend'
    ui_dir = plugin_dir / 'ui'
    backend_dir.mkdir(exist_ok=True)
    ui_dir.mkdir(exist_ok=True)
    # Keep existing manifest.json, but add a plugin.json mirror only if absent.
    plugin_json = plugin_dir / 'plugin.json'
    if not plugin_json.exists():
        out = dict(data)
        out.setdefault('compatible_api', '1.x')
        out.setdefault('entry_backend', out.get('entrypoint', 'plugin:Plugin'))
        if (plugin_dir / 'ui' / 'index.js').exists():
            out.setdefault('entry_ui', 'ui/index.js')
        plugin_json.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
PY
fi

say "Updating entry script if needed"
ENTRY=bin/ultimate-kea-dashboard-plugin
if [[ -f "$ENTRY" ]]; then
  if (( DRY_RUN )); then
    echo "DRY-RUN: patch $ENTRY import path"
  else
    python3 <<'PY'
from pathlib import Path
path = Path('bin/ultimate-kea-dashboard-plugin')
text = path.read_text(encoding='utf-8')
text = text.replace('from lib.plugin_runtime import PluginRuntime', 'from core.plugin_runtime import PluginRuntime')
path.write_text(text, encoding='utf-8')
PY
  fi
fi

say "Attempting to remove lib/ if empty"
if [[ -d lib ]]; then
  if (( DRY_RUN )); then
    echo "DRY-RUN: remove lib if empty"
  else
    find lib -type d -empty -delete || true
    if [[ -d lib ]] && [[ -z "$(find lib -mindepth 1 -print -quit 2>/dev/null)" ]]; then
      rmdir lib || true
    fi
  fi
fi

say "Creating architecture boundary note"
ARCH=docs/refactor-layout-notes.md
if [[ ! -f "$ARCH" ]]; then
  if (( DRY_RUN )); then
    echo "DRY-RUN: create $ARCH"
  else
    cat > "$ARCH" <<'DOC'
# Refactor layout notes

Target ownership rules:

- `core/` owns platform and plugin runtime concerns.
- `server/` owns built-in backend concerns.
- `plugins/` owns optional feature packages.
- `ui/` owns frontend source and browser logic.
- `assets/` owns passive files only.

Manual follow-up still required:

1. Audit `static/js/`.
2. Move app logic into `ui/`.
3. Move passive/vendor files into `assets/js/`.
4. Delete `static/` once empty.
5. Run app smoke tests.
DOC
  fi
fi

say "Refactor pass complete"
cat <<'OUT'

Next checks to run locally:

  rg "from lib\\.|import lib\\.|from plugin_system import" .
  rg "static/" .
  git status

Recommended follow-up:

1. Inspect static/js manually.
2. Move real UI logic into ui/.
3. Move vendor/passive JS into assets/js/vendor/.
4. Run the app and smoke-test plugins.
5. Commit in phases, for example:
   - refactor(core): move plugin runtime and API into core
   - refactor(server): move backend services into server layer
   - refactor(ui): move themes/translations and disentangle static js
   - chore: update scripts and packaging for new layout

OUT
