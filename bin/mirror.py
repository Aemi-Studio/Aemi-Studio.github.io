#!/usr/bin/env python3
"""
Mirror source files into the build output directory, excluding
build-only files (source-fonts/, bin/, _data/, .git/, build artefacts).

Replaces the `rsync -a --exclude=...` call from bin/build.sh because
Cloudflare Pages' build container does not ship rsync. Pure stdlib —
runs on any Python 3.10+.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Top-level entries to skip during the mirror.
EXCLUDES = {
    "docs",
    ".git",
    ".github",
    "node_modules",
    ".bundle",
    "source-fonts",
    "bin",
    "_data",
    "build.fish",
    "requirements.txt",
    ".vscode",
    ".gitignore",
    ".DS_Store",
    "__pycache__",
    "README.md",
    "LICENSE",
}


def is_excluded(rel_parts: tuple[str, ...]) -> bool:
    if not rel_parts:
        return False
    head = rel_parts[0]
    if head in EXCLUDES:
        return True
    # Catch nested .DS_Store / __pycache__ anywhere in the tree.
    for part in rel_parts:
        if part == ".DS_Store" or part == "__pycache__":
            return True
    return False


def mirror(src: Path, dst: Path) -> int:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    n_files = 0
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        if is_excluded(rel.parts):
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            n_files += 1
    return n_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror source into build output, with excludes (rsync replacement).")
    parser.add_argument("--src", type=Path, required=True, help="Source directory")
    parser.add_argument("--dst", type=Path, required=True, help="Destination directory")
    args = parser.parse_args()

    src = args.src.resolve()
    dst = args.dst.resolve()
    if not src.is_dir():
        sys.stderr.write(f"mirror: source not found: {src}\n")
        return 1
    n = mirror(src, dst)
    print(f"mirror: copied {n} files from {src} to {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
