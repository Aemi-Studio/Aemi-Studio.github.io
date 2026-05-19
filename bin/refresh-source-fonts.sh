#!/usr/bin/env bash
#
# macOS-only helper to refresh source-fonts/ from the latest SF Pro DMG
# and the upstream JetBrains Mono GitHub release.
#
# Run periodically (~quarterly) when Apple ships a new SF Pro:
#   bin/refresh-source-fonts.sh
#   git add source-fonts && git commit -m "Refresh source fonts" && git push
#
# Cloudflare Pages does NOT run this — it consumes whatever the
# committed source-fonts/ already has.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEST_DIR="$PROJECT_ROOT/source-fonts"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "refresh-source-fonts: macOS-only (needs hdiutil/pkgutil)" >&2
    exit 1
fi
mkdir -p "$DEST_DIR"

WORK="$(mktemp -d -t aemi-studio-fonts)"
trap 'rm -rf "$WORK"' EXIT

# ----- SF Pro -----
SFPRO_URL="https://devimages-cdn.apple.com/design/resources/download/SF-Pro.dmg"
DMG="$WORK/SF-Pro.dmg"
MOUNT="$WORK/sf-pro-mount"

echo "▸ downloading SF Pro from Apple…"
curl -fsSL -o "$DMG" "$SFPRO_URL"

echo "▸ mounting DMG…"
mkdir -p "$MOUNT"
hdiutil attach -readonly -nobrowse -mountpoint "$MOUNT" "$DMG" >/dev/null

echo "▸ expanding PKG…"
PKG="$(find "$MOUNT" -name '*.pkg' | head -1)"
EXPAND="$WORK/expand"
pkgutil --expand-full "$PKG" "$EXPAND"

echo "▸ converting masters to WOFF2…"
for stem in SF-Pro SF-Pro-Italic SFNS SFNSItalic SFNS-Italic; do
    ttf="$(find "$EXPAND" -name "${stem}.ttf" -print -quit 2>/dev/null || true)"
    if [[ -n "$ttf" ]]; then
        case "$stem" in
            *Italic*) out="$DEST_DIR/SFPro-Italic.woff2" ;;
            *)        out="$DEST_DIR/SFPro.woff2" ;;
        esac
        echo "    $ttf -> $out"
        python3 -c "
from fontTools.ttLib import TTFont
f = TTFont('$ttf')
f.flavor = 'woff2'
f.save('$out')
"
    fi
done

hdiutil detach "$MOUNT" >/dev/null 2>&1 || true

# ----- JetBrains Mono -----
JBM_BASE="https://github.com/JetBrains/JetBrainsMono/raw/refs/heads/master/fonts/variable"
echo "▸ refreshing JetBrains Mono Variable from GitHub…"
curl -fsSL -o "$WORK/JetBrainsMono.ttf"        "$JBM_BASE/JetBrainsMono%5Bwght%5D.ttf"
curl -fsSL -o "$WORK/JetBrainsMono-Italic.ttf" "$JBM_BASE/JetBrainsMono-Italic%5Bwght%5D.ttf"
python3 -c "
from fontTools.ttLib import TTFont
for ttf, out in [
    ('$WORK/JetBrainsMono.ttf',        '$DEST_DIR/JetBrainsMono.woff2'),
    ('$WORK/JetBrainsMono-Italic.ttf', '$DEST_DIR/JetBrainsMono-Italic.woff2'),
]:
    f = TTFont(ttf)
    f.flavor = 'woff2'
    f.save(out)
    print(f'    {ttf} -> {out}')
"

echo
echo "▸ result:"
ls -lh "$DEST_DIR"/*.woff2
