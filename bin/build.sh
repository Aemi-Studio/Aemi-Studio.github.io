#!/usr/bin/env bash
#
# Cross-platform build for aemi.studio.
#
# Replaces the macOS-only build.fish. Runs on macOS and on Cloudflare
# Pages' Ubuntu build container (and any CI with bash + node + python3).
#
# Pipeline:
#   1. Clean docs/ and mirror source into it via rsync.
#   2. Substitute {{ symbol:NAME }} placeholders with SF Symbols PUA
#      codepoints from _data/sfsymbols.json.
#   3. Minify every .css in docs/ (clean-css via npx; cached in CI).
#   4. Minify every .html in docs/ (html-minifier-terser via npx;
#      same flag set as the old minhtml call but cross-platform).
#   5. Add intrinsic width/height + decoding="async" to every <img>.
#   6. Install fontTools + brotli; thin SF Pro + JetBrains Mono masters
#      from source-fonts/ into docs/resources/fonts/ based on the actual
#      codepoints used in the built HTML/CSS/SVG.
#   7. Postbuild structural check.
#
# Exit non-zero on any step's failure so CF Pages aborts a bad build.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCS="$PROJECT_ROOT/docs"
cd "$PROJECT_ROOT"

step() { printf "\n\033[1;34m▸ %s\033[0m\n" "$*"; }

step "mirror source into docs/"
rm -rf "$DOCS"
mkdir -p "$DOCS"
# Excludes mirror build.fish's old behaviour plus the new build artefacts.
rsync -a \
    --exclude=docs \
    --exclude=.git \
    --exclude=.github \
    --exclude=node_modules \
    --exclude=.bundle \
    --exclude=source-fonts \
    --exclude=bin \
    --exclude=_data \
    --exclude=build.fish \
    --exclude=requirements.txt \
    --exclude='*.DS_Store' \
    --exclude=.vscode \
    --exclude='.gitignore' \
    "$PROJECT_ROOT/" "$DOCS/"

step "substitute SF Symbol placeholders in HTML"
python3 "$SCRIPT_DIR/inline-symbols.py" --site "$DOCS" --symbols "$PROJECT_ROOT/_data/sfsymbols.json"

step "minify CSS"
# Use npx so CI doesn't need a manual `npm install -g`. --no-install
# would error on missing package, but npx fetches on demand.
for css in "$DOCS"/resources/styles/*.css; do
    npx --yes clean-css-cli@5 -o "$css" "$css" >/dev/null
done

step "minify HTML"
for html in $(find "$DOCS" -name '*.html'); do
    npx --yes html-minifier-terser@7 \
        --collapse-whitespace \
        --remove-comments \
        --remove-redundant-attributes \
        --remove-script-type-attributes \
        --remove-style-link-type-attributes \
        --use-short-doctype \
        --minify-css true \
        --minify-js true \
        -o "$html" "$html" >/dev/null
done

step "add width/height/decoding to <img>"
python3 "$SCRIPT_DIR/annotate-images.py" --site "$DOCS"

step "install Python font-subset deps"
python3 -m pip install --user --quiet --disable-pip-version-check -r "$PROJECT_ROOT/requirements.txt"

step "thin SF Pro + JetBrains Mono into docs/resources/fonts/"
python3 "$SCRIPT_DIR/subset-fonts.py" --site "$DOCS" --source-fonts "$PROJECT_ROOT/source-fonts" --out "$DOCS/resources/fonts"

step "postbuild sanity check"
"$SCRIPT_DIR/postbuild-check.sh" "$DOCS"

printf "\n\033[1;32m✓ build complete: %s\033[0m\n" "$(du -sh "$DOCS" | cut -f1)"
