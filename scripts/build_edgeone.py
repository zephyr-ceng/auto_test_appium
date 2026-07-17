from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
PAGES_DIR = ROOT / "frontend" / "pages"
ASSETS_DIR = ROOT / "frontend" / "assets"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing required source directory: {source}")
    shutil.copytree(source, target, dirs_exist_ok=True)


def main() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    DIST_DIR.mkdir(parents=True)
    copy_tree(PAGES_DIR, DIST_DIR)
    copy_tree(ASSETS_DIR, DIST_DIR / "static")


if __name__ == "__main__":
    main()
