#!/usr/bin/env bash
#
# Postbuild sanity check for aemi.studio. Fast structural verifications
# that catch typical regressions before Cloudflare publishes.
#
# Exit non-zero on any failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SITE="${1:-$PROJECT_ROOT/docs}"

fail() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }
ok()   { printf "\033[1;32m  ✓ %s\033[0m\n" "$*"; }

[[ -d "$SITE" ]] || fail "build dir missing: $SITE"
[[ -f "$SITE/index.html" ]] || fail "$SITE/index.html missing"
[[ -f "$SITE/_headers" ]]   || fail "$SITE/_headers missing"
[[ -f "$SITE/_redirects" ]] || fail "$SITE/_redirects missing"
ok "site skeleton present"

# Every @font-face URL referenced from CSS must resolve to a file in the
# build output. Catches the case where the thinner failed silently.
missing=0
while IFS= read -r url; do
    rel="${url#/}"
    if [[ ! -f "$SITE/$rel" ]]; then
        printf "    missing: %s\n" "$url"
        missing=$((missing + 1))
    fi
done < <(grep -hoE '/resources/fonts/[A-Za-z0-9._-]+\.woff2' "$SITE"/resources/styles/*.css 2>/dev/null | sort -u)
(( missing == 0 )) || fail "$missing font file(s) referenced by CSS not on disk"
ok "all font URLs resolve to files"

for f in "$SITE/resources/fonts/"*.woff2; do
    [[ -s "$f" ]] || fail "empty font file: $f"
done
ok "font files are non-empty"

# Cheap regression grep — these have bitten us before.
if grep -q 'Sun, 31 Dec 2025' "$SITE/_headers"; then
    fail "_headers still contains past-dated Expires"
fi
if grep -qE 'browsing-topics=|interest-cohort=' "$SITE/_headers"; then
    fail "_headers still has deprecated Permissions-Policy directives"
fi
if grep -qE 'X-UA-Compatible' "$SITE/_headers"; then
    fail "_headers still has obsolete X-UA-Compatible"
fi
if grep -qE 'Cross-Origin-Embedder-Policy: require-corp' "$SITE/_headers"; then
    fail "_headers still sets require-corp COEP"
fi
ok "no known header regressions"

# Unsubstituted SF Symbol placeholders are bugs.
if grep -rqE '\{\{\s*symbol:' "$SITE" --include='*.html'; then
    fail "unsubstituted {{ symbol:... }} placeholders found in HTML"
fi
ok "no unsubstituted symbol placeholders"

printf "\033[1;32m✓ postbuild checks passed\033[0m\n"
