#!/usr/bin/env python3
"""
Annotate every <img> tag in the built HTML with intrinsic width/height
and decoding="async". Cuts CLS to ~zero without changing visible markup.

We use a regex pass over HTML instead of a real parser because the
build output is already minified at this point and a real parser would
re-format it. We only touch <img> tags that lack width/height/decoding.

Dimensions come from the actual image file via Pillow if available,
falling back to `file`-style header inspection (PNG/JPEG/WebP).
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent

IMG_RE = re.compile(
    r"""<img\b(?P<attrs>[^>]*)>""",
    re.IGNORECASE,
)
SRC_RE = re.compile(r"""\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
ATTR_RE = lambda name: re.compile(rf"""\b{name}\s*=""", re.IGNORECASE)


def png_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    return None


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(data)
    while i + 1 < n:
        if data[i] != 0xFF:
            return None
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return None
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9):
            return None
        if 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > n:
            return None
        seg_len = struct.unpack(">H", data[i:i + 2])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            return w, h
        i += seg_len
    return None


def webp_size(data: bytes) -> tuple[int, int] | None:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8 ":
        w = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        h = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return w, h
    if chunk == b"VP8L":
        b0, b1, b2, b3 = data[21:25]
        w = ((b1 & 0x3F) << 8 | b0) + 1
        h = (((b3 & 0xF) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6)) + 1
        return w, h
    if chunk == b"VP8X":
        w = (data[24] | data[25] << 8 | data[26] << 16) + 1
        h = (data[27] | data[28] << 8 | data[29] << 16) + 1
        return w, h
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        head = path.read_bytes()[:64 * 1024]
    except OSError:
        return None
    for fn in (png_size, jpeg_size, webp_size):
        size = fn(head)
        if size:
            return size
    return None


def annotate_one(html_path: Path, site_root: Path) -> int:
    text = html_path.read_text(encoding="utf-8")
    edits = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal edits
        attrs = match.group("attrs")
        src_match = SRC_RE.search(attrs)
        if not src_match:
            return match.group(0)
        src = src_match.group(1) or src_match.group(2) or src_match.group(3)
        if not src or src.startswith(("data:", "http://", "https://", "//")):
            extra = []
        else:
            extra = []
            rel = src.lstrip("/")
            asset = site_root / rel
            if asset.exists():
                size = image_size(asset)
                if size and not ATTR_RE("width").search(attrs):
                    extra.append(f'width="{size[0]}"')
                if size and not ATTR_RE("height").search(attrs):
                    extra.append(f'height="{size[1]}"')
        if not ATTR_RE("decoding").search(attrs):
            extra.append('decoding="async"')
        if not extra:
            return match.group(0)
        edits += 1
        new_attrs = attrs.rstrip()
        prefix = "" if new_attrs.endswith(("'", '"')) or new_attrs == "" else " "
        return f"<img{new_attrs}{prefix} {' '.join(extra)}>"

    new_text = IMG_RE.sub(repl, text)
    if edits:
        html_path.write_text(new_text, encoding="utf-8")
    return edits


def main() -> int:
    parser = argparse.ArgumentParser(description="Add width/height/decoding=async to every <img>.")
    parser.add_argument("--site", type=Path, default=PROJECT_ROOT / "docs", help="Built site directory")
    args = parser.parse_args()

    site_dir: Path = args.site.resolve()
    if not site_dir.is_dir():
        sys.stderr.write(f"annotate-images: site dir not found: {site_dir}\n")
        return 1

    total = 0
    for html in site_dir.rglob("*.html"):
        total += annotate_one(html, site_dir)
    print(f"annotate-images: annotated {total} <img> tags in {site_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
