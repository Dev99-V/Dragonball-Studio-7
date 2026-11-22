#!/usr/bin/env bash
set -euo pipefail

# Build Godot 4.7.2 Windows x86_64 release + NSIS setup.exe installer on Linux (0d, no Windows runner needed).
# Output: build/windows/dr7-studio-setup.exe (+ .sha256 & windows-build-meta.json)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_VER="$(tr -d '[:space:]' < "$ROOT_DIR/VERSION")"
GODOT_BIN="$ROOT_DIR/tools/godot/godot"
TEMPLATE_DIR="$HOME/.local/share/godot/export_templates/4.7.2.stable"
STAGE_DIR="$ROOT_DIR/build/windows/stage"
OUT_SETUP="$ROOT_DIR/build/windows/dr7-studio-setup.exe"
ICON_PATH="$ROOT_DIR/assets/app_icon/dr7_studio.ico"

if ! command -v makensis >/dev/null 2>&1; then
  echo "[FAIL] Chua cai 'makensis' (NSIS). Cai nhanh tren Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y nsis" >&2
  exit 1
fi

if [ ! -x "$GODOT_BIN" ] || [ ! -f "$TEMPLATE_DIR/windows_release_x86_64.exe" ]; then
  echo "[win-setup] Dang tu dong tai Godot 4.7.2 + Export Templates cho Windows Desktop..."
  bash "$ROOT_DIR/tools/godot/install_godot.sh" --with-templates
fi

if [ ! -f "$ICON_PATH" ]; then
  echo "[win-setup] Dang tao $ICON_PATH tu assets/app_icon/icon_512.png..."
  python3 - "$ROOT_DIR/assets/app_icon/icon_512.png" "$ICON_PATH" <<'PY'
import pathlib, sys
from PIL import Image
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
img = Image.open(src).convert("RGBA")
img.save(dst, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
PY
fi

mkdir -p "$ROOT_DIR/build/windows"
touch "$ROOT_DIR/build/.gdignore"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

echo "[1/3] Importing & exporting Godot 4.7.2 Windows Desktop (x86_64, Compatibility)..."
"$GODOT_BIN" --headless --path "$ROOT_DIR" --editor --import >/dev/null
"$GODOT_BIN" --headless --path "$ROOT_DIR" --export-release "Windows Desktop" "$STAGE_DIR/DR7-Studio.exe"

test -f "$STAGE_DIR/DR7-Studio.exe"
test -f "$STAGE_DIR/DR7-Studio.pck"

echo "[2/3] Packing NSIS installer (LZMA solid) -> $OUT_SETUP..."
rm -f "$OUT_SETUP"
makensis -V2 \
  "-DAPP_VERSION=$APP_VER" \
  "-DSTAGE_DIR=$STAGE_DIR" \
  "-DICON_PATH=$ICON_PATH" \
  "-DOUT_FILE=$OUT_SETUP" \
  "$ROOT_DIR/tools/windows/installer.nsi"

test -f "$OUT_SETUP"

echo "[3/3] Computing SHA-256 & metadata..."
sha256sum "$OUT_SETUP" | tee "${OUT_SETUP}.sha256"
python3 - "$ROOT_DIR" "$APP_VER" "$STAGE_DIR" "$OUT_SETUP" <<'PY'
import hashlib, json, pathlib, sys

root = pathlib.Path(sys.argv[1])
ver = sys.argv[2]
stage = pathlib.Path(sys.argv[3])
setup = pathlib.Path(sys.argv[4])
exe = stage / "DR7-Studio.exe"
pck = stage / "DR7-Studio.pck"

def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

meta = {
    "version": ver,
    "arch": "x86_64",
    "setup_bytes": setup.stat().st_size,
    "setup_sha256": sha256(setup),
    "exe_bytes": exe.stat().st_size,
    "exe_sha256": sha256(exe),
    "pck_bytes": pck.stat().st_size,
    "pck_sha256": sha256(pck),
}
out_meta = root / "build" / "windows" / "windows-build-meta.json"
out_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(f"[OK] Windows setup.exe san sang: {setup} ({meta['setup_bytes']} B | PCK={meta['pck_bytes']} B)")
PY
