"""create_game_template.py

Copy the files from `template/` into `games/<game_id>/` and substitute
simple placeholders (e.g. ${GAME_NAME}, ${GAME_ID}, ${AUTHOR}, ${VERSION}).

Usage:
  python create_game_template.py --name "My Game" [--id my_game] [--author NAME]

This is intentionally minimal and safe for local developer use.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from string import Template
from datetime import datetime


ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "template"
# Place generated games in `clients/developer_client/games` so template and generated
# games live together for developer convenience.
GAMES_DIR = ROOT / "games"
PLACEHOLDER_SUFFIXES = {".py", ".md", ".txt", ".json", ".cfg", ".ini"}


def slugify(name: str) -> str:
    # very small slug: keep alnum, -, _
    import re

    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    s = re.sub(r"_+", "_", s)
    return s.strip("_").lower()


def render_file(path: Path, ctx: dict):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        # binary or unreadable — skip
        return
    try:
        rendered = Template(text).safe_substitute(ctx)
    except Exception:
        # If templating fails, leave original
        return
    path.write_text(rendered, encoding="utf-8")


def create_package_init(dst: Path) -> None:
    # ensure package importability by adding __init__.py in the top-level game folder
    init = dst / "__init__.py"
    if not init.exists():
        init.write_text("# game package\n", encoding="utf-8")


def copy_template(dst: Path, ctx: dict, overwrite: bool = False) -> None:
    if dst.exists():
        if not overwrite:
            raise FileExistsError(f"Destination already exists: {dst}")
        # remove it entirely to get a clean copy
        shutil.rmtree(dst)

    shutil.copytree(TEMPLATE_DIR, dst)
    create_package_init(dst)

    # substitute placeholders in text files
    for p in dst.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in PLACEHOLDER_SUFFIXES:
                render_file(p, ctx)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create a new game from template")
    ap.add_argument("--name", required=True, help="Display name of the game")
    ap.add_argument("--id", help="Game id (folder name). Defaults to slugified name")
    ap.add_argument("--author", default="anonymous", help="Author name")
    ap.add_argument("--version", default="0.1.0", help="Initial version")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing target")
    args = ap.parse_args(argv)

    if not TEMPLATE_DIR.exists():
        print(f"Template folder not found: {TEMPLATE_DIR}")
        return 2

    game_name = args.name
    game_id = args.id or slugify(game_name)
    author = args.author
    version = args.version

    dst = GAMES_DIR / game_id
    ctx = {
        "GAME_NAME": game_name,
        "GAME_ID": game_id,
        "AUTHOR": author,
        "VERSION": version,
        "YEAR": str(datetime.now().year),
    }

    # ensure the games directory exists before copying the template
    try:
        GAMES_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Failed to create games directory {GAMES_DIR}: {e}")
        return 5

    try:
        copy_template(dst, ctx, overwrite=args.overwrite)
    except FileExistsError as e:
        print(f"Error: {e}")
        return 3
    except Exception as e:
        print(f"Failed to create template: {e}")
        return 4

    print(f"Created game at: {dst}")
    print("Next steps:")
    print(f"  - cd {dst}")
    print(f"  - run the local server/client (see README or run_local.py in the new game folder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
