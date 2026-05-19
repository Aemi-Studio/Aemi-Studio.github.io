#!/usr/bin/env python3
"""
Build-time font thinning (subsetting) for aemi.studio.

Reads master variable WOFF2 files from source-fonts/, extracts the
unique Unicode codepoints actually used in the generated docs/, and
writes each thinned font to docs/resources/fonts/<name>.woff2.

Goals:
1. Always thin: every build produces a subset with only the glyphs the
   site ships, plus a small ASCII + typographic baseline. Variable
   axes (wght, wdth, opsz, ital, YAXS) are preserved so CSS can still
   request the full weight/width range.
2. Cheap codepoint extraction: tight loop over text files into a set.
3. Keep SF Symbol PUA codepoints: any glyph injected via
   bin/inline-symbols.py lands in the built HTML as a real character,
   so the same extraction pass that finds Latin text keeps the symbols
   without any allowlist.
4. Cross-platform: pure Python 3.10+ + fonttools[woff2] + brotli.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

try:
    from fontTools.subset import Options, Subsetter, load_font, save_font
except ImportError:
    sys.stderr.write(
        "subset-fonts: fontTools is required.\n"
        "  Install with: python3 -m pip install --user fonttools brotli\n"
    )
    sys.exit(2)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

FONTS = (
    {"out": "SFPro.woff2",                "src": "SFPro.woff2"},
    {"out": "SFPro-Italic.woff2",         "src": "SFPro-Italic.woff2"},
    {"out": "JetBrainsMono.woff2",        "src": "JetBrainsMono.woff2"},
    {"out": "JetBrainsMono-Italic.woff2", "src": "JetBrainsMono-Italic.woff2"},
)

_ASCII = set(range(0x20, 0x7F))
_TYPO = {0xA0, 0x00A9, 0x00AE, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2122, 0x00AB, 0x00BB}
_FR_DIACRITICS = {ord(c) for c in "àâäçèéêëîïôöùûüÿœæÀÂÄÇÈÉÊËÎÏÔÖÙÛÜŸŒÆ"}
ALWAYS_KEEP = _ASCII | _TYPO | _FR_DIACRITICS


def extract_codepoints(site_dir: Path) -> set[int]:
    codepoints: set[int] = set()
    for pattern in ("*.html", "*.css", "*.svg", "*.xml"):
        for path in site_dir.rglob(pattern):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            codepoints.update(ord(ch) for ch in text)
    return codepoints


def make_options() -> Options:
    opts = Options()
    opts.flavor = "woff2"
    opts.with_zopfli = False
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.name_languages = ["*"]
    opts.glyph_names = False
    opts.legacy_kern = False
    opts.symbol_cmap = False
    opts.notdef_outline = True
    opts.recommended_glyphs = True
    opts.recalc_bounds = True
    opts.recalc_timestamp = False
    opts.canonical_order = True
    opts.hinting = True
    opts.passthrough_tables = False
    opts.drop_tables = [
        "EBLC", "EBDT", "EBSC",                    # bitmap embedding
        "Silf", "Glat", "Gloc", "Feat", "Sill",    # Graphite (Linux only)
        "FFTM",                                    # FontForge timestamp
        "PfEd",                                    # FontForge private
        "TSI0", "TSI1", "TSI2", "TSI3", "TSI5",    # TrueType inspector hints
    ]
    return opts


def thin(src: Path, dst: Path, codepoints: set[int]) -> tuple[int, int]:
    opts = make_options()
    font = load_font(str(src), opts, lazy=False, dontLoadGlyphNames=False)
    subsetter = Subsetter(options=opts)
    subsetter.populate(unicodes=sorted(codepoints))
    subsetter.subset(font)
    save_font(font, str(dst), opts)
    font.close()
    return src.stat().st_size, dst.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin master fonts to actually-used codepoints.")
    parser.add_argument("--site", type=Path, default=PROJECT_ROOT / "docs", help="Built site directory to scan for codepoints")
    parser.add_argument("--source-fonts", type=Path, default=PROJECT_ROOT / "source-fonts", help="Directory containing master WOFF2 files")
    parser.add_argument("--out", type=Path, default=None, help="Output directory (defaults to <site>/resources/fonts)")
    parser.add_argument("--keep-everything", action="store_true", help="Skip subsetting; copy masters verbatim (debug)")
    args = parser.parse_args()

    site_dir: Path = args.site.resolve()
    source_dir: Path = args.source_fonts.resolve()
    if not site_dir.is_dir():
        sys.stderr.write(f"subset-fonts: site dir not found: {site_dir}\n")
        return 1
    if not source_dir.is_dir():
        sys.stderr.write(f"subset-fonts: source-fonts dir not found: {source_dir}\n")
        return 1

    out_dir: Path = (args.out or site_dir / "resources" / "fonts").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    codepoints = ALWAYS_KEEP | extract_codepoints(site_dir)
    print(f"subset-fonts: scanned {site_dir} -> {len(codepoints)} unique codepoints (incl. {len(ALWAYS_KEEP)} baseline)")

    total_in = total_out = 0
    for entry in FONTS:
        src = source_dir / entry["src"]
        dst = out_dir / entry["out"]
        if not src.exists():
            print(f"  skip   {entry['out']:<28} source missing ({src})")
            continue
        if args.keep_everything:
            shutil.copyfile(src, dst)
            sz = dst.stat().st_size
            total_in += sz
            total_out += sz
            print(f"  copy   {entry['out']:<28} {sz:>10,} B (no subset, debug)")
            continue
        try:
            t0 = time.perf_counter()
            in_size, out_size = thin(src, dst, codepoints)
            dt_ms = (time.perf_counter() - t0) * 1000
            ratio = (1 - out_size / in_size) * 100 if in_size else 0
            total_in += in_size
            total_out += out_size
            print(f"  thin   {entry['out']:<28} {in_size:>10,} -> {out_size:>8,} B  (-{ratio:5.1f}%, {dt_ms:5.0f} ms)")
        except Exception as exc:
            sys.stderr.write(f"subset-fonts: failed to thin {entry['src']}: {exc}\n")
            shutil.copyfile(src, dst)
            sz = dst.stat().st_size
            total_in += sz
            total_out += sz

    if total_in > 0:
        saving = (1 - total_out / total_in) * 100
        print(f"subset-fonts: total {total_in:,} -> {total_out:,} B ({saving:.1f}% saved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
