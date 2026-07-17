from __future__ import annotations

import shutil
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
PAGES_DIR = ROOT / "frontend" / "pages"
ASSETS_DIR = ROOT / "frontend" / "assets"
PYENV_ROOT = ROOT / ".edgeone_pyenv"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing required source directory: {source}")
    shutil.copytree(source, target, dirs_exist_ok=True)


def main() -> None:
    install_dependencies()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    DIST_DIR.mkdir(parents=True)
    copy_tree(PAGES_DIR, DIST_DIR)
    copy_tree(ASSETS_DIR, DIST_DIR / "static")


def install_dependencies() -> None:
    if dependencies_available():
        return

    env = os.environ.copy()
    env.setdefault("PYENV_ROOT", str(PYENV_ROOT))
    PYENV_ROOT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(ROOT / "requirements.txt"),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )


def dependencies_available() -> bool:
    try:
        import fastapi  # noqa: F401
        import pydantic  # noqa: F401
        import requests  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    main()
