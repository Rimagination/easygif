"""Verify that frame-to-frame changes stay inside an approved motion region."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def masked_mean(image: Image.Image, mask: Image.Image) -> float:
    if mask.getbbox() is None:
        return 0.0
    values = ImageStat.Stat(image, mask=mask).mean
    return sum(values) / len(values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report and validate whether adjacent frame changes stay within a bounding-box region."
    )
    parser.add_argument("frames", type=Path)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    target.add_argument("--mask", type=Path, help="grayscale mask image; white is allowed to change")
    parser.add_argument("--max-outside-ratio", type=float, default=0.20)
    parser.add_argument("--max-outside-delta", type=float, default=1.0)
    args = parser.parse_args()
    if args.max_outside_ratio < 0 or args.max_outside_delta < 0:
        raise SystemExit("outside thresholds must be non-negative")
    paths = sorted(path for path in args.frames.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    if len(paths) < 2:
        raise SystemExit("at least two frames are required")

    images = []
    try:
        for path in paths:
            with Image.open(path) as source:
                images.append(source.convert("RGB"))
        size = images[0].size
        if any(image.size != size for image in images):
            raise SystemExit("all frames must have the same dimensions")
        if args.region:
            x, y, width, height = args.region
            if width <= 0 or height <= 0 or x < 0 or y < 0:
                raise SystemExit("region must be a positive x y width height rectangle")
            if x + width > size[0] or y + height > size[1]:
                raise SystemExit(f"region {args.region} exceeds frame size {size}")
            inside = Image.new("L", size, 0)
            inside.paste(255, (x, y, x + width, y + height))
            region_description: object = [x, y, width, height]
        else:
            with Image.open(args.mask) as source:
                inside = source.convert("L")
            if inside.size != size:
                raise SystemExit(f"mask {args.mask} has size {inside.size}, expected {size}")
            if inside.getbbox() is None:
                raise SystemExit("mask must contain at least one non-black pixel")
            region_description = {"mask": str(args.mask)}
        outside = ImageChops.invert(inside)
        pairs = []
        violations = []
        for index, (left, right) in enumerate(zip(images, images[1:])):
            diff = ImageChops.difference(left, right)
            inside_delta = masked_mean(diff, inside)
            outside_delta = masked_mean(diff, outside)
            allowed = max(args.max_outside_delta, inside_delta * args.max_outside_ratio)
            item = {
                "boundary": index + 1,
                "inside_delta": round(inside_delta, 4),
                "outside_delta": round(outside_delta, 4),
                "allowed_outside_delta": round(allowed, 4),
                "outside_ratio": round(outside_delta / max(inside_delta, 1e-6), 4),
            }
            pairs.append(item)
            if outside_delta > allowed:
                violations.append(index + 1)

        report = {
            "frames": len(paths),
            "size": list(size),
            "region": region_description,
            "max_outside_ratio": args.max_outside_ratio,
            "max_outside_delta": args.max_outside_delta,
            "pairs": pairs,
            "violations": violations,
            "passed": not violations,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if violations:
            raise SystemExit(1)
    finally:
        for image in images:
            image.close()


if __name__ == "__main__":
    main()
