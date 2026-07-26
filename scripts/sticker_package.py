"""Shared profile, image inspection, and package validation helpers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "references" / "platforms"


def natural_key(path: Path) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def load_profile(value: str | Path) -> dict[str, Any]:
    candidate = Path(value)
    if not candidate.suffix:
        candidate = PROFILE_DIR / f"{value}.json"
    if not candidate.is_file():
        raise SystemExit(f"platform profile not found: {value}")
    try:
        profile = json.loads(candidate.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid platform profile {candidate}: {exc}") from exc
    if not isinstance(profile, dict) or profile.get("schema") != "easygif/platform-profile-v1":
        raise SystemExit(f"unsupported platform profile: {candidate}")
    return profile


def inspect_media(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "exists": False, "errors": ["file not found"]}
    result: dict[str, Any] = {
        "path": str(path),
        "exists": True,
        "bytes": path.stat().st_size,
        "suffix": path.suffix.lower(),
        "errors": [],
    }
    try:
        with Image.open(path) as image:
            image.load()
            durations: list[int] = []
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                durations.append(max(0, int(image.info.get("duration", 0))))
            result.update({
                "format": image.format or path.suffix.lstrip(".").upper(),
                "size": list(image.size),
                "frames": getattr(image, "n_frames", 1),
                "alpha": "A" in image.getbands() or image.info.get("transparency") is not None,
                "duration_ms": sum(durations) if durations else 0,
                "loop": image.info.get("loop"),
            })
    except Exception as exc:  # Pillow raises several format-specific errors.
        result["errors"].append(str(exc))
    return result


def _check_dimension(media: dict[str, Any], spec: dict[str, Any], label: str, errors: list[str], warnings: list[str]) -> None:
    expected = [spec.get("width"), spec.get("height")]
    if not all(value is not None for value in expected) or "size" not in media:
        return
    actual = media["size"]
    if actual != expected:
        message = f"{label}: size {actual[0]}x{actual[1]} != {expected[0]}x{expected[1]}"
        (errors if spec.get("strict", False) else warnings).append(message)


def validate_main_media(media: dict[str, Any], profile: dict[str, Any], label: str) -> tuple[list[str], list[str]]:
    errors = list(media.get("errors", []))
    warnings: list[str] = []
    spec = profile.get("main", {})
    if not media.get("exists"):
        return errors, warnings
    if media.get("format") not in spec.get("formats", []):
        errors.append(f"{label}: format {media.get('format')} is not one of {spec.get('formats', [])}")
    max_bytes = spec.get("max_bytes")
    if max_bytes and media.get("bytes", 0) > max_bytes:
        errors.append(f"{label}: bytes {media['bytes']} > {max_bytes}")
    max_duration = spec.get("max_duration_ms")
    if max_duration and media.get("duration_ms", 0) > max_duration:
        errors.append(f"{label}: duration {media['duration_ms']}ms > {max_duration}ms")
    if profile.get("strict"):
        dimension_spec = {**spec, "strict": True}
        _check_dimension(media, dimension_spec, label, errors, warnings)
    elif spec.get("width") and spec.get("height"):
        _check_dimension(media, spec, label, errors, warnings)
    return errors, warnings


def validate_package(root: Path, profile: dict[str, Any]) -> dict[str, Any]:
    sticker_dir = root / "stickers"
    paths = sorted(
        [path for path in sticker_dir.iterdir() if path.is_file()] if sticker_dir.is_dir() else [],
        key=natural_key,
    )
    errors: list[str] = []
    warnings: list[str] = []
    items = []
    set_spec = profile.get("set", {})
    count = len(paths)
    if count < set_spec.get("min_items", 1):
        errors.append(f"sticker count {count} < {set_spec['min_items']}")
    if count > set_spec.get("max_items", 10**9):
        errors.append(f"sticker count {count} > {set_spec['max_items']}")
    allowed = set_spec.get("allowed_counts", [])
    if allowed and count not in allowed:
        errors.append(f"sticker count {count} is not one of {allowed}")
    for path in paths:
        media = inspect_media(path)
        item_errors, item_warnings = validate_main_media(media, profile, path.name)
        errors.extend(item_errors)
        warnings.extend(item_warnings)
        items.append(media)

    for name, spec in profile.get("derived_assets", {}).items():
        if name == "item_icon":
            icon_paths = sorted(
                (root / "assets" / "icons").glob("*.png") if (root / "assets" / "icons").is_dir() else [],
                key=natural_key,
            )
            if len(icon_paths) != count:
                warnings.append(f"item icon count {len(icon_paths)} != sticker count {count}")
            for path in icon_paths:
                media = inspect_media(path)
                if media.get("format") != spec.get("format", "PNG"):
                    errors.append(f"{path.relative_to(root)}: format {media.get('format')} != {spec.get('format')}")
                if media.get("size") != [spec["width"], spec["height"]]:
                    errors.append(f"{path.relative_to(root)}: size {media.get('size')} != {[spec['width'], spec['height']]}")
                if spec.get("max_bytes") and media.get("bytes", 0) > spec["max_bytes"]:
                    errors.append(f"{path.relative_to(root)}: bytes {media['bytes']} > {spec['max_bytes']}")
            continue
        path = root / "assets" / f"{name}.png"
        if not path.is_file():
            if spec.get("required"):
                errors.append(f"missing required asset: assets/{name}.png")
            else:
                warnings.append(f"missing optional asset: assets/{name}.png")
            continue
        media = inspect_media(path)
        if media.get("format") != spec.get("format", "PNG"):
            errors.append(f"assets/{name}.png: format {media.get('format')} != {spec.get('format')}")
        if "width" in spec and media.get("size") != [spec["width"], spec["height"]]:
            errors.append(f"assets/{name}.png: size {media.get('size')} != {[spec['width'], spec['height']]}")
        if spec.get("max_bytes") and media.get("bytes", 0) > spec["max_bytes"]:
            errors.append(f"assets/{name}.png: bytes {media['bytes']} > {spec['max_bytes']}")

    return {
        "schema": "easygif/sticker-package-validation-v1",
        "profile": profile.get("id"),
        "root": str(root),
        "count": count,
        "items": items,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }


def render_png(source: Path, destination: Path, size: tuple[int, int]) -> None:
    with Image.open(source) as image:
        image.seek(0)
        frame = image.convert("RGBA")
        fitted = ImageOps.contain(frame, size, method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.alpha_composite(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
        destination.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(destination, format="PNG", optimize=True)
        fitted.close()
        frame.close()
