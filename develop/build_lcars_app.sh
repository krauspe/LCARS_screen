#!/bin/zsh
# =============================================================================
#  build_lcars_app.sh — Rebuild the LCARS.app macOS launcher with custom icon
#
#  This script produces a double-clickable AppleScript applet (NOT a real
#  compiled/packaged app) that launches the LCARS PySide6 app invisibly —
#  no Terminal, no flashing window.
#
#  Key steps, all of which are REQUIRED on Apple Silicon:
#    1. osacompile the .applescript  →  proper applet bundle structure
#    2. Generate a multi-size .icns  →  custom desktop icon
#    3. Ad-hoc code sign             →  unsigned apps are blocked on Apple Silicon
#    4. Clear the quarantine flag    →  avoids "not allowed on this Mac"
#
#  Usage:
#    zsh build_lcars_app.sh
#
#  Output:
#    <project>/LCARS_build.app   (signed, with icon)
#    — then drag it into place via Finder (see notes below).
#
#  NOTE on the Desktop permission issue:
#    macOS protects an already-launched/registered app inside ~/Desktop, so
#    overwriting or deleting it from a shell (even from VS Code) fails with
#    "Operation not permitted". Build to the project folder, then swap via
#    Finder (drag old app to Trash, drag LCARS_build.app to Desktop).
# =============================================================================

set -euo pipefail

# Directory of this script (project root / develop)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Project root = one level up from develop/
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APPLESCRIPT="$PROJECT_DIR/LCARS_launcher.applescript"
ICON_PNG="$PROJECT_DIR/lcars-icon.png"
OUT_APP="$PROJECT_DIR/LCARS_build.app"

echo "==> Project dir : $PROJECT_DIR"
echo "==> AppleScript : $APPLESCRIPT"
echo "==> Icon PNG    : $ICON_PNG"
echo "==> Output app  : $OUT_APP"

# ── Sanity checks ────────────────────────────────────────────────────────────
[ -f "$APPLESCRIPT" ] || { echo "ERROR: $APPLESCRIPT not found"; exit 1; }
[ -f "$ICON_PNG" ]     || { echo "ERROR: $ICON_PNG not found"; exit 1; }
command -v osacompile >/dev/null || { echo "ERROR: osacompile not found"; exit 1; }
command -v iconutil   >/dev/null || { echo "ERROR: iconutil not found"; exit 1; }
command -v sips       >/dev/null || { echo "ERROR: sips not found"; exit 1; }
command -v codesign   >/dev/null || { echo "ERROR: codesign not found"; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── 1. Build the .icns icon from the PNG ──────────────────────────────────────
echo "==> Generating .icns from $ICON_PNG"
ICONSET="$WORK/lcars.iconset"
mkdir -p "$ICONSET"
sips -z  16   16 "$ICON_PNG" --out "$ICONSET/icon_16x16.png"       >/dev/null
sips -z  32   32 "$ICON_PNG" --out "$ICONSET/icon_16x16@2x.png"    >/dev/null
sips -z  32   32 "$ICON_PNG" --out "$ICONSET/icon_32x32.png"       >/dev/null
sips -z  64   64 "$ICON_PNG" --out "$ICONSET/icon_32x32@2x.png"    >/dev/null
sips -z 128  128 "$ICON_PNG" --out "$ICONSET/icon_128x128.png"     >/dev/null
sips -z 256  256 "$ICON_PNG" --out "$ICONSET/icon_128x128@2x.png"  >/dev/null
sips -z 256  256 "$ICON_PNG" --out "$ICONSET/icon_256x256.png"     >/dev/null
sips -z 512  512 "$ICON_PNG" --out "$ICONSET/icon_256x256@2x.png"  >/dev/null
sips -z 512  512 "$ICON_PNG" --out "$ICONSET/icon_512x512.png"     >/dev/null
sips -z 1024 1024 "$ICON_PNG" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o "$WORK/lcars.icns"

# ── 2. Compile the AppleScript applet ─────────────────────────────────────────
echo "==> Compiling AppleScript applet"
rm -rf "$OUT_APP"
osacompile -o "$OUT_APP" "$APPLESCRIPT"

# ── 3. Inject the custom icon + fix the icon look-up ──────────────────────────
echo "==> Installing custom icon"
cp "$WORK/lcars.icns" "$OUT_APP/Contents/Resources/applet.icns"

# Remove the asset-catalog icon reference & its file. Otherwise modern macOS
# reads the icon from Assets.car (default grey applet) and IGNORES applet.icns.
rm -f "$OUT_APP/Contents/Resources/Assets.car"
rm -f "$OUT_APP/Contents/Resources/applet.rsrc"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$OUT_APP/Contents/Info.plist" 2>/dev/null || true

# Give the bundle a clean, stable name (osacompile names it after the .applescript).
/usr/libexec/PlistBuddy -c "Set :CFBundleName LCARS" "$OUT_APP/Contents/Info.plist"

# ── 4. Ad-hoc code sign (REQUIRED on Apple Silicon) ───────────────────────────
echo "==> Ad-hoc code signing"
codesign --force --deep --sign - "$OUT_APP"

# ── 5. Clear the quarantine attribute ─────────────────────────────────────────
echo "==> Clearing quarantine attribute"
xattr -dr com.apple.quarantine "$OUT_APP" 2>/dev/null || true

echo ""
echo "✅ Done. Built: $OUT_APP"
echo "   Next: drag $OUT_APP to your Desktop via Finder,"
echo "   replacing any existing LCARS.app (Finder has the needed permissions)."