#!/usr/bin/env python3
"""Stage the linked static site assets for GitHub Pages without deleting repo files."""
from __future__ import annotations

import json
import subprocess
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
CODE_SUFFIXES = {".html", ".js", ".css", ".svg", ".json", ".xml"}
# Latest paths are assembled dynamically by cards(folder, files).
# Resolve these at runtime below; a text search alone is insufficient.
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
    latest = (ROOT / "latest.html").read_text()
    start = latest.index("    const ratios=")
    end = latest.index("    const root=document.documentElement;", start)
    projects = json.loads(subprocess.check_output(
        ["node", "-e", latest[start:end] + "\nconsole.log(JSON.stringify(projects));"], text=True))
    required = set()
    preview_dirs = set()
    for project in projects:
        for card in project["cards"]:
            required.update(card[key] for key in ("src", "thumb") if not card[key].startswith("http"))
        required.update(path for path in project.get("bookPdfs", []) if path)
        preview_dirs.update(path.rstrip("/") + "/" for path in project.get("bookPreviewDirs", []) if path)
    # Resolve cards(folder, files) before considering any Latest asset unused.
    for path in required:
        if not (ROOT / path).is_file():
            raise SystemExit(f"Referenced media missing: {path}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(ROOT, destination, ignore=ignored)

    removed: list[Path] = []
    for asset_dir in (*ASSET_DIRS, "latest-assets", "latest-thumbs"):
        folder = destination / asset_dir
        if not folder.exists():
            continue
        for asset in folder.rglob("*"):
            if not asset.is_file():
                continue
            relative = asset.relative_to(destination).as_posix()
            if relative not in code and relative not in required and not any(relative.startswith(d) for d in preview_dirs):
                asset.unlink()
                removed.append(asset)
        for subdir in sorted((path for path in folder.rglob("*") if path.is_dir()), reverse=True):
            try:
                subdir.rmdir()
            except OSError:
                pass

    for path in required:
        if not (destination / path).is_file():
            raise SystemExit(f"Staging removed required media: {path}")
    print(f"Verified {len(required)} resolved Latest media paths and all book preview folders.")
    size = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    print(f"Staged {size:,} bytes for Pages; omitted {len(removed)} unreferenced files from media asset folders.")
    print("All omitted source files remain in the Git repository.")
    if size >= MAX_PAGES_BYTES:
        raise SystemExit(f"Pages package exceeds the 1 GB limit ({MAX_PAGES_BYTES:,} bytes).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_pages.py <destination>")
    stage(Path(sys.argv[1]).resolve())
