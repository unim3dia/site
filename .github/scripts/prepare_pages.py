#!/usr/bin/env python3
"""Stage the linked static site assets for GitHub Pages without deleting repo files."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
CODE_SUFFIXES = {".html", ".js", ".css", ".svg", ".json", ".xml"}
ASSET_DIRS = ("ai", "media")
MAX_PAGES_BYTES = 1_000_000_000


def read_site_code() -> str:
    parts: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "_site", "node_modules"} for part in path.parts):
            continue
        if path.suffix.lower() in CODE_SUFFIXES:
            parts.append(path.read_text(errors="ignore"))
    return unquote("\n".join(parts)).replace("\\'", "'")


def ignored(directory: str, names: list[str]) -> set[str]:
    current = Path(directory)
    return {name for name in names if name in {".git", ".github", ".claude", ".DS_Store", "node_modules"}}


def stage(destination: Path) -> None:
    code = read_site_code()
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT, destination, ignore=ignored)

    removed: list[Path] = []
    for asset_dir in ASSET_DIRS:
        folder = destination / asset_dir
        if not folder.exists():
            continue
        for asset in folder.rglob("*"):
            if not asset.is_file():
                continue
            relative = asset.relative_to(destination).as_posix()
            if relative not in code:
                asset.unlink()
                removed.append(asset)
        for subdir in sorted((path for path in folder.rglob("*") if path.is_dir()), reverse=True):
            try:
                subdir.rmdir()
            except OSError:
                pass

    size = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    print(f"Staged {size:,} bytes for Pages; omitted {len(removed)} unreferenced files from ai/ and media/.")
    print("All omitted source files remain in the Git repository.")
    if size >= MAX_PAGES_BYTES:
        raise SystemExit(f"Pages package exceeds the 1 GB limit ({MAX_PAGES_BYTES:,} bytes).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_pages.py <destination>")
    stage(Path(sys.argv[1]).resolve())
