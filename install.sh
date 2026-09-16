#!/usr/bin/env bash
#
# install.sh — build FeederCable.exe from source and install it on this machine.
#
# Run from Git Bash on the Windows box that will host the station:
#
#     ./install.sh                  # build, install, provision, verify
#     ./install.sh --build-only     # produce dist/FeederCable, install nothing
#     ./install.sh --install-only   # install an already-built dist/FeederCable
#     ./install.sh --init-db        # also create the MySQL schema
#     ./install.sh --help           # every option
#
# The app is frozen as a PyInstaller *onedir* bundle, not onefile, and that is
# deliberate. Every module resolves its data through os.path.dirname(__file__)
# and several of those files are written at runtime -- camera_cfg.ini,
# comport_cfg.ini, vision_config.json, the taught models under vision_models/,
# the per-PASS images under vision_captures/, the TEMPPRN/TEMPMARKER/TEMPLOTPRN
# label scratch files. Under onefile that directory is a temp folder the loader
# deletes on exit, so every camera calibration, COM port assignment and taught
# part would be thrown away when the operator closed the app. Onedir puts it in
# a real folder that persists.

set -euo pipefail

APP_NAME="FeederCable"
ENTRY="main.py"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

DEFAULT_DEST="${LOCALAPPDATA:-$HOME/AppData/Local}/Programs/$APP_NAME"

DO_BUILD=1
DO_INSTALL=1
MAKE_SHORTCUTS=1
CLEAN=0
CONSOLE=0
ALL_DEPS=0
INIT_DB=0
SEED_FROM_REPO=0
DEST=""

usage() {
    cat <<'USAGE'
Usage: ./install.sh [options]

  --build-only        Build dist/FeederCable and stop.
  --install-only      Skip the build; install whatever is in dist/FeederCable.
  --dest <path>       Install location. Default: %LOCALAPPDATA%\Programs\FeederCable
  --no-shortcut       Do not create Desktop / Start Menu shortcuts.
  --clean             Delete build/ and dist/ before building.
  --init-db           Run init_db.py after installing, to create the MySQL
                      schema. Needs MySQL reachable with db.py's credentials.
  --seed-from-repo    Provision the station's config by copying this checkout's
                      camera_cfg.ini, vision_config.json and vision_models/
                      verbatim, instead of writing neutral defaults. Use it to
                      clone a known-good station; see "Provisioning" below.
  --console           Build a debug exe that keeps a console window open. The
                      app prints [PLC DEBUG], [HIPOT DEBUG] and [VISION DEBUG]
                      lines to stdout; the default windowed build discards them,
                      so use this when diagnosing a fixture on the line.
  --all-deps          Install requirements.txt verbatim, including ultralytics.
                      Off by default: nothing in this codebase imports
                      ultralytics, and it pulls in torch (~2.5 GB).
  -h, --help          Show this message.

Provisioning
  After the payload is copied, the installer creates every runtime file the app
  needs and does not ship: comport_cfg.ini, camera_cfg.ini, vision_config.json,
  emp.txt, vision_models/ and vision_captures/. A file that already exists is
  never touched, so re-running this over a live station keeps its assigned COM
  ports, calibrated cameras and taught parts.

  The defaults are neutral -- no COM ports assigned, no cameras enabled, no
  parts mapped -- because this checkout's own config describes a developer
  machine, and a station that silently inherited camera index 1 or a taught
  part it does not run would inspect against the wrong reference. Fill them in
  from COM Port Settings and Vision Settings on first run, or pass
  --seed-from-repo to copy this checkout's values instead.
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        --build-only)     DO_INSTALL=0 ;;
        --install-only)   DO_BUILD=0 ;;
        --dest)           DEST="${2:?--dest needs a path}"; shift ;;
        --no-shortcut)    MAKE_SHORTCUTS=0 ;;
        --clean)          CLEAN=1 ;;
        --init-db)        INIT_DB=1 ;;
        --seed-from-repo) SEED_FROM_REPO=1 ;;
        --console)        CONSOLE=1 ;;
        --all-deps)       ALL_DEPS=1 ;;
        -h|--help)        usage; exit 0 ;;
        *)                echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

DEST="${DEST:-$DEFAULT_DEST}"
VPY=".venv/Scripts/python.exe"

say()  { printf '\n==> %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
warn() { printf '    WARNING: %s\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# ── One run at a time ────────────────────────────────────────────────────────
# Two concurrent runs share .venv, and pip halfway through installing a package
# while another pip reads the same site-packages fails with WinError 32 and can
# leave the environment half-written. mkdir is atomic, so it makes a usable lock.
LOCK_DIR="$HERE/.install.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    die "Another install.sh is already running (lock: $LOCK_DIR).
       If no other run is active, delete that directory and try again."
fi
cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

# ── What the frozen app needs beside itself ──────────────────────────────────
# Read-only assets, shipped inside the bundle. Label templates are chosen per
# part in Model Settings, so every .prn ships -- a part whose template is
# missing falls back to TEMPPRN.prn and prints the wrong label. The three
# date code tables ship with them, for the same reason: a station missing
# one falls back to the built-in scheme and prints a code nobody chose.
ASSET_FILES=(
    "BARCODE FINAL.prn"
    "DATAMATRIX FINAL.prn"
    "HMI BARCODE .prn"
    "LOTPRN.prn"
    "MARKER.prn"
    "TEMPMARKER_START.prn"
    "TEMPPRN.prn"
    "VW DATAMATRIX.prn"
    "nice DATAMATRIX1.prn"
    "DAY CODE.txt"
    "MONTH CODE.txt"
    "YEAR CODE.txt"
    "OK.WAV"
    "NG.WAV"
    "FC EOL.ico"
)
# Station state. Created by the installer if absent, never overwritten.
CONFIG_FILES=("comport_cfg.ini" "camera_cfg.ini" "vision_config.json" "emp.txt")
STATE_DIRS=("vision_models" "vision_captures")

ICON="FC EOL.ico"

# ── Build ────────────────────────────────────────────────────────────────────
if [ "$DO_BUILD" = 1 ]; then
    say "Locating Python"
    PY=""
    for candidate in "py -3" python python3; do
        if $candidate --version >/dev/null 2>&1; then PY="$candidate"; break; fi
    done
    [ -n "$PY" ] || die "No Python found on PATH. Install Python 3.10+ and re-run."
    note "$($PY --version 2>&1) — $($PY -c 'import sys; print(sys.executable)')"

    $PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
        || die "Python 3.10 or newer is required."
    $PY -c 'import tkinter' 2>/dev/null \
        || die "This Python has no tkinter. Re-run the installer and tick 'tcl/tk and IDLE'."

    say "Preparing virtual environment (.venv)"
    [ -d .venv ] || $PY -m venv .venv
    [ -f "$VPY" ] || die ".venv looks broken — delete it and re-run."

    "$VPY" -m pip install --upgrade pip --quiet

    say "Installing dependencies"
    if [ "$ALL_DEPS" = 1 ]; then
        "$VPY" -m pip install -r requirements.txt
    else
        # requirements.txt minus ultralytics. Nothing imports it, and it drags
        # torch in behind it. --all-deps restores the file verbatim.
        grep -viE '^[[:space:]]*ultralytics' requirements.txt > .venv/requirements.build.txt
        "$VPY" -m pip install -r .venv/requirements.build.txt
        note "ultralytics skipped (unused by this codebase). Use --all-deps to include it."
    fi
    "$VPY" -m pip install --upgrade "pyinstaller>=6.0"

    if [ "$CLEAN" = 1 ]; then
        say "Cleaning previous build output"
        rm -rf build dist "$APP_NAME.spec"
    fi

    say "Freezing $ENTRY"
    ARGS=(--noconfirm --onedir --name "$APP_NAME")
    [ -f "$ICON" ] && ARGS+=(--icon "$ICON")
    if [ "$CONSOLE" = 1 ]; then ARGS+=(--console); else ARGS+=(--windowed); fi

    for f in "${ASSET_FILES[@]}"; do
        if [ -f "$f" ]; then ARGS+=(--add-data "$f;."); else warn "asset missing, not bundled: $f"; fi
    done

    # PyInstaller's scanner follows imports, and these are reached in ways it
    # cannot see: plugin lookups, lazy backends and Pillow's Tk bridge.
    for hidden in \
        serial.tools.list_ports \
        pymodbus.framer \
        mysql.connector.locales.eng.client_error \
        mysql.connector.plugins.mysql_native_password \
        win32print win32timezone \
        PIL._tkinter_finder
    do
        ARGS+=(--hidden-import "$hidden")
    done

    # Pulled in transitively but never used here. Left in, the bundle grows by
    # gigabytes for code that never runs.
    for excl in ultralytics torch torchvision torchaudio matplotlib scipy \
                pandas PyQt5 PyQt6 PySide2 PySide6 notebook IPython pytest
    do
        ARGS+=(--exclude-module "$excl")
    done

    "$VPY" -m PyInstaller "${ARGS[@]}" "$ENTRY"

    [ -f "dist/$APP_NAME/$APP_NAME.exe" ] || die "Build finished but dist/$APP_NAME/$APP_NAME.exe is missing."
    say "Built dist/$APP_NAME/$APP_NAME.exe"
    note "$(du -sh "dist/$APP_NAME" 2>/dev/null | cut -f1) on disk"
fi

[ "$DO_INSTALL" = 1 ] || exit 0

# ── Install the payload ──────────────────────────────────────────────────────
[ -d "dist/$APP_NAME" ] || die "dist/$APP_NAME not found. Run without --install-only first."

case "$(printf '%s' "$DEST" | tr 'A-Z' 'a-z')" in
    */program\ files*|*/program\ files\ \(x86\)*)
        warn "$DEST is under Program Files, which standard users cannot write to."
        warn "The app writes its config and label scratch files beside the exe, so"
        warn "it will fail there unless operators run as administrator." ;;
esac

say "Installing to $DEST"
# PyInstaller 6 puts bundled data under _internal/, which is also where
# dirname(__file__) resolves to for a frozen module -- so that is the folder
# the app reads and writes its config in.
SUB=""
[ -d "dist/$APP_NAME/_internal" ] && SUB="/_internal"

KEEP=""
if [ -e "$DEST/$APP_NAME.exe" ]; then
    note "Existing install found — upgrading in place."
    # A station's config is earned: COM ports assigned, cameras calibrated,
    # parts taught, a year of pass images. Hold it aside and put it back over
    # the fresh payload rather than letting the copy bury it.
    KEEP="$(mktemp -d)"
    src="$DEST$SUB"
    for c in "${CONFIG_FILES[@]}"; do
        if [ -f "$src/$c" ]; then cp -p "$src/$c" "$KEEP/"; note "keeping $c"; fi
    done
    for d in "${STATE_DIRS[@]}"; do
        if [ -d "$src/$d" ]; then cp -r "$src/$d" "$KEEP/"; note "keeping $d/"; fi
    done
fi

mkdir -p "$DEST"
cp -r "dist/$APP_NAME/." "$DEST/"

PAYLOAD="$DEST$SUB"
if [ -n "$KEEP" ]; then
    cp -rp "$KEEP/." "$PAYLOAD/" 2>/dev/null || true
    rm -rf "$KEEP"
    note "Station config restored."
fi

# ── Provision the runtime files ──────────────────────────────────────────────
# Everything below is create-if-absent. Nothing here overwrites a file that is
# already on the station.
say "Provisioning runtime files in $PAYLOAD"

seed_file() {
    # seed_file <name> <what-created-it>; body on stdin. Skips if present.
    local name="$1" what="$2"
    if [ -f "$PAYLOAD/$name" ]; then
        note "kept      $name (already present)"
        cat >/dev/null
        return
    fi
    cat > "$PAYLOAD/$name"
    note "created   $name  ($what)"
}

copy_from_repo() {
    local name="$1"
    if [ -f "$PAYLOAD/$name" ]; then note "kept      $name (already present)"; return 1; fi
    if [ -f "$HERE/$name" ]; then
        cp -p "$HERE/$name" "$PAYLOAD/$name"
        note "created   $name  (copied from this checkout)"
        return 0
    fi
    return 1
}

# comport_cfg.ini — every device COM Port Settings knows about, plus the three
# keys the test console reads directly. Ports are "0" (unassigned) rather than
# a guess: a wrong COM number opens somebody else's device.
seed_file "comport_cfg.ini" "unassigned ports — set them in COM Port Settings" <<'CFG'
[COM]
hp_port = 0
hp_baud = 9600
lcr_port = 0
lcr_baud = 9600
plc_port = 0
plc_baud = 9600
io_port = 0
io_baud = 9600
ioc_port = 0
ioc_baud = 9600
printer_port = 0
printer_baud = 9600
scanner_port = 0
scanner_baud = 9600
machine_id = PB1
scan_enabled = True
lot_label_enabled = True
CFG

if [ "$SEED_FROM_REPO" = 1 ]; then
    copy_from_repo "camera_cfg.ini"    || true
    copy_from_repo "vision_config.json" || true
else
    # Both cameras off and index -1. Enabling a camera the station may not have
    # would fail every vision check before the electrical tests ever ran.
    seed_file "camera_cfg.ini" "cameras off — enable them in Vision Settings" <<'CFG'
[CAMERA]
cam1_index = -1
cam2_index = -1
cam1_width = 640
cam1_height = 480
cam2_width = 640
cam2_height = 480
cam1_enabled = False
cam2_enabled = False
CFG

    # Empty part_mapping. A part with no model logs "no vision model configured"
    # and skips vision; a part mapped to somebody else's taught model would be
    # judged against the wrong reference, which is worse.
    seed_file "vision_config.json" "no parts taught yet — teach them in Vision Settings" <<'CFG'
{
    "vision_enabled": true,
    "camera_source": "cam1",
    "match_threshold": 0.75,
    "part_mapping": {}
}
CFG
fi

# emp.txt gates the Employee ID field. _validate_employee() returns True when
# the file is missing, so an absent emp.txt silently accepts any ID typed at
# the console -- the file has to exist even if the site fills it in later.
if ! copy_from_repo "emp.txt"; then
    if [ ! -f "$PAYLOAD/emp.txt" ]; then
        printf '' > "$PAYLOAD/emp.txt"
        note "created   emp.txt  (EMPTY — add the site's employee numbers, comma separated)"
        warn "emp.txt is empty, so every Employee ID will be rejected until it is filled in."
    fi
fi

for d in "${STATE_DIRS[@]}"; do
    if [ -d "$PAYLOAD/$d" ]; then
        note "kept      $d/ ($(find "$PAYLOAD/$d" -type f 2>/dev/null | wc -l | tr -d ' ') files)"
    else
        mkdir -p "$PAYLOAD/$d"
        note "created   $d/"
    fi
done
if [ "$SEED_FROM_REPO" = 1 ] && [ -d "$HERE/vision_models" ]; then
    cp -rn "$HERE/vision_models/." "$PAYLOAD/vision_models/" 2>/dev/null || true
    note "seeded    vision_models/ from this checkout"
fi

# ── Verify ───────────────────────────────────────────────────────────────────
say "Verifying the install"
MISSING=0
check() {
    if [ -e "$PAYLOAD/$1" ] || [ -e "$DEST/$1" ]; then
        printf '    ok       %s\n' "$1"
    else
        printf '    MISSING  %s\n' "$1"; MISSING=$((MISSING + 1))
    fi
}
check "$APP_NAME.exe"
for f in "${ASSET_FILES[@]}"; do check "$f"; done
for c in "${CONFIG_FILES[@]}"; do check "$c"; done
for d in "${STATE_DIRS[@]}"; do check "$d"; done

# The app writes TEMPPRN.prn and friends here on every print; if this folder is
# not writable the operator finds out at the first PASS, mid-shift.
if ( : > "$PAYLOAD/.writetest" ) 2>/dev/null; then
    rm -f "$PAYLOAD/.writetest"
    printf '    ok       %s is writable\n' "$PAYLOAD"
else
    printf '    MISSING  %s is NOT writable — label printing and settings will fail\n' "$PAYLOAD"
    MISSING=$((MISSING + 1))
fi

[ "$MISSING" -eq 0 ] || die "$MISSING required item(s) missing — see the list above."

# ── Database ─────────────────────────────────────────────────────────────────
if [ "$INIT_DB" = 1 ]; then
    say "Creating the MySQL schema (init_db.py)"
    if [ -f "$VPY" ]; then
        "$VPY" init_db.py || die "init_db.py failed. Check that MySQL is running and db.py's credentials are right."
    else
        die "--init-db needs the build virtualenv. Run without --install-only, or run 'python init_db.py' yourself."
    fi
fi

# ── Shortcuts ────────────────────────────────────────────────────────────────
if [ "$MAKE_SHORTCUTS" = 1 ]; then
    say "Creating shortcuts"
    WIN_DEST="$(cygpath -w "$DEST")"
    WIN_EXE="$WIN_DEST\\$APP_NAME.exe"

    powershell -NoProfile -NonInteractive -Command "
        \$ws = New-Object -ComObject WScript.Shell
        \$targets = @(
            [System.Environment]::GetFolderPath('Desktop'),
            (Join-Path \$env:APPDATA 'Microsoft\Windows\Start Menu\Programs')
        )
        foreach (\$dir in \$targets) {
            if (-not (Test-Path \$dir)) { continue }
            \$path = Join-Path \$dir '$APP_NAME.lnk'
            \$lnk = \$ws.CreateShortcut(\$path)
            \$lnk.TargetPath       = '$WIN_EXE'
            \$lnk.WorkingDirectory = '$WIN_DEST'
            \$lnk.IconLocation     = '$WIN_EXE'
            \$lnk.Description      = 'Feeder Cable EOL test station'
            \$lnk.Save()
            Write-Host ('    shortcut: ' + \$path)
        }
    " || warn "Shortcut creation failed — the install itself is fine."
fi

say "Installed"
note "$DEST/$APP_NAME.exe"
note "config and state: $PAYLOAD"

cat <<'POST'

    Still to do on a new station:
      1. MySQL must be reachable with db.py's credentials (localhost / feeder
         / root). Re-run with --init-db to create the schema.
      2. COM Port Settings — assign the Delta PLC and HiPot ports.
      3. Vision Settings — enable the cameras and teach each part.
      4. emp.txt — add the site's employee numbers if it is still empty.
      5. Windows printers named EOLPRINTER (part labels) and LOTPRINTER
         (box labels) must exist, spelled exactly.
POST
