#!/usr/bin/env python3
"""
Inline SF Symbol PUA codepoints into the built HTML.

Reads `_data/sfsymbols.json` (a list of [name, glyph] pairs) and walks
every .html file in the build output, replacing occurrences of the
`{{ symbol:NAME }}` template with the corresponding PUA glyph. Unknown
names render a visible `?` so typos surface during review.

Symbols can be used anywhere in HTML:

    <i class="sf-symbol">{{ symbol:house.fill }}</i>

The substitution happens before minification so resulting bytes are
already inside the served HTML — no runtime JS needed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

PLACEHOLDER_RE = re.compile(r"\{\{\s*symbol:([\w.\-]+)\s*\}\}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Substitute {{ symbol:NAME }} placeholders with SF Symbol PUA glyphs.")
    parser.add_argument("--site", type=Path, default=PROJECT_ROOT / "docs", help="Built site directory")
    parser.add_argument("--symbols", type=Path, default=PROJECT_ROOT / "_data" / "sfsymbols.json", help="JSON mapping of name -> PUA glyph")
    args = parser.parse_args()

    site_dir: Path = args.site.resolve()
    symbols_path: Path = args.symbols.resolve()

    if not site_dir.is_dir():
        sys.stderr.write(f"inline-symbols: site dir not found: {site_dir}\n")
        return 1
    if not symbols_path.exists():
        sys.stderr.write(f"inline-symbols: sfsymbols.json not found: {symbols_path}\n")
        return 1

    raw = json.loads(symbols_path.read_text(encoding="utf-8"))
    table: dict[str, str] = dict(raw)
    print(f"inline-symbols: loaded {len(table)} symbols")

    total_replaced = 0
    missing: set[str] = set()
    for html in site_dir.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        if "{{" not in text:
            continue
        def sub(match: re.Match[str]) -> str:
            nonlocal total_replaced
            name = match.group(1)
            glyph = table.get(name)
            if glyph is None:
                missing.add(name)
                return "?"
            total_replaced += 1
            return glyph
        new_text, count = PLACEHOLDER_RE.subn(sub, text)
        if count:
            html.write_text(new_text, encoding="utf-8")
    if missing:
        for name in sorted(missing):
            sys.stderr.write(f"inline-symbols: WARNING unknown symbol '{name}' (rendered as '?')\n")
    print(f"inline-symbols: substituted {total_replaced} occurrences across {site_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
