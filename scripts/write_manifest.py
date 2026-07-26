"""Write a compact, machine-readable manifest beside a media deliverable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def describe_media(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"output not found: {path}")
    result: dict[str, object] = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "suffix": path.suffix.lower(),
    }
    with Image.open(path) as image:
        image.load()
        result.update({
            "format": image.format,
            "size": list(image.size),
            "frames": getattr(image, "n_frames", 1),
            "mode": image.mode,
            "alpha": "A" in image.getbands(),
            "loop": image.info.get("loop"),
            "duration_ms": image.info.get("duration"),
        })
    return result


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid JSON report {path}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--plan", type=Path, help="compiled plan JSON")
    parser.add_argument("--validation", type=Path, action="append", default=[])
    parser.add_argument("--motion-concept", default="unspecified")
    parser.add_argument("--strategy", default="unspecified")
    parser.add_argument("--platform-profile", default=None)
    parser.add_argument("--reference-lock", type=Path)
    parser.add_argument("--note", action="append", default=[])
    args = parser.parse_args()

    manifest = {
        "schema": "easygif/manifest-v1",
        "media": describe_media(args.output),
        "source": describe_media(args.source) if args.source else None,
        "motion": {"concept": args.motion_concept},
        "strategy": args.strategy,
        "platform_profile": args.platform_profile,
        "reference_lock": load_json(args.reference_lock) if args.reference_lock else None,
        "plan": load_json(args.plan) if args.plan else None,
        "validation": {
            path.stem: load_json(path)
            for path in args.validation
        },
        "notes": args.note,
    }
    target = args.manifest or args.output.with_name("manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote manifest to {target}")


if __name__ == "__main__":
    main()
