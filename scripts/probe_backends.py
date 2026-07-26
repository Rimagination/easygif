"""Probe optional local media backends without installing or mutating them."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def command_info(name: str) -> dict[str, object]:
    path = shutil.which(name)
    return {"available": bool(path), "path": path}


def directory_info(path: Path | None) -> dict[str, object]:
    return {"available": bool(path and path.is_dir()), "path": str(path) if path else None}


def file_info(path: Path | None) -> dict[str, object]:
    return {"available": bool(path and path.is_file()), "path": str(path) if path else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--film-python", type=Path)
    parser.add_argument("--film-repo", type=Path)
    parser.add_argument("--film-model", type=Path)
    args = parser.parse_args()

    film_python = args.film_python or args.project_root / ".local" / "tools" / "film-venv" / "Scripts" / "python.exe"
    film_repo = args.film_repo or args.project_root / ".local" / "tools" / "frame-interpolation"
    film_model = args.film_model or args.project_root / ".local" / "models" / "film" / "film_net" / "Style" / "saved_model"
    pillow = importlib.util.find_spec("PIL") is not None
    ffmpeg = command_info("ffmpeg")
    gifski = command_info("gifski")
    film = {
        "python": file_info(film_python),
        "repo": directory_info(film_repo),
        "model": directory_info(film_model),
    }
    film["available"] = all(item["available"] for item in film.values())
    backends = {
        "pillow_or_gifski": pillow or bool(gifski["available"]),
        "ffmpeg_extract": bool(ffmpeg["available"]),
        "gifski": bool(gifski["available"]),
        "film_opaque": film["available"],
        "film_opaque_crop": film["available"],
        "imagegen_contact_sheet": "host-provided",
        "keyframe_generator": "host-provided",
        "local_rgba_composite": pillow,
        "validated_grid_slice": pillow,
    }
    print(json.dumps({
        "schema": "easygif/backend-probe-v1",
        "project_root": str(args.project_root),
        "python": {"pillow": pillow},
        "commands": {"ffmpeg": ffmpeg, "gifski": gifski},
        "film": film,
        "backends": backends,
        "notes": [
            "host-provided means the Codex/image-generation capability is expected from the calling environment",
            "probe is read-only; install or configure optional tools outside this command",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
