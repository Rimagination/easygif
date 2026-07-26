"""Validate a static-base composite for outside drift and mask-edge spill."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def masked_mean(image: Image.Image, mask: Image.Image) -> float:
    if mask.getbbox() is None:
        return 0.0
    values = ImageStat.Stat(image, mask=mask).mean
    return sum(values) / len(values)


def binary_mask(source: Image.Image, threshold: int) -> Image.Image:
    return source.convert("L").point(lambda value: 255 if value > threshold else 0)


def mask_for_region(size: tuple[int, int], region: tuple[int, int, int, int]) -> Image.Image:
    x, y, width, height = region
    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > size[0] or y + height > size[1]:
        raise SystemExit(f"region {region} exceeds frame size {size}")
    mask = Image.new("L", size, 0)
    mask.paste(255, (x, y, x + width, y + height))
    return mask


def image_paths(path: Path) -> list[Path]:
    if not path.is_dir():
        raise SystemExit(f"expected a frame directory: {path}")
    paths = sorted(item for item in path.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES)
    if len(paths) < 2:
        raise SystemExit("at least two composited frames are required")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check static-base composites for background drift and seam spill around the approved mask."
    )
    parser.add_argument("base", type=Path)
    parser.add_argument("frames", type=Path)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"))
    target.add_argument("--mask", type=Path, help="grayscale mask; white is allowed to change")
    parser.add_argument("--mask-threshold", type=int, default=8)
    parser.add_argument("--ring-radius", type=int, default=2)
    parser.add_argument("--max-outside-delta", type=float, default=1.0)
    parser.add_argument("--max-boundary-delta", type=float, default=2.0)
    args = parser.parse_args()
    if not 0 <= args.mask_threshold <= 255:
        raise SystemExit("mask-threshold must be between 0 and 255")
    if args.ring_radius < 1:
        raise SystemExit("ring-radius must be at least 1")
    if args.max_outside_delta < 0 or args.max_boundary_delta < 0:
        raise SystemExit("delta thresholds must be non-negative")

    paths = image_paths(args.frames)
    with Image.open(args.base) as source:
        base = source.convert("RGB")
    approved = None
    try:
        if args.region:
            approved = mask_for_region(base.size, tuple(args.region))
            region_description: object = list(args.region)
        else:
            with Image.open(args.mask) as source:
                approved = binary_mask(source, args.mask_threshold)
            if approved.size != base.size:
                raise SystemExit(f"mask {args.mask} has size {approved.size}, expected {base.size}")
            region_description = {"mask": str(args.mask), "threshold": args.mask_threshold}
        if approved.getbbox() is None:
            raise SystemExit("approved region must contain at least one non-black pixel")

        kernel = args.ring_radius * 2 + 1
        expanded = approved.filter(ImageFilter.MaxFilter(kernel))
        outside = ImageChops.invert(approved)
        boundary_outside = ImageChops.subtract(expanded, approved)
        if outside.getbbox() is None:
            raise SystemExit("approved region covers the whole frame; outside drift cannot be validated")

        pairs = []
        violations = []
        for index, path in enumerate(paths):
            with Image.open(path) as source:
                frame = source.convert("RGB")
            try:
                if frame.size != base.size:
                    raise SystemExit(f"frame {path} has size {frame.size}, expected {base.size}")
                diff = ImageChops.difference(base, frame)
                outside_delta = masked_mean(diff, outside)
                boundary_delta = masked_mean(diff, boundary_outside)
                item = {
                    "frame": index + 1,
                    "path": str(path),
                    "outside_delta": round(outside_delta, 4),
                    "boundary_outside_delta": round(boundary_delta, 4),
                    "allowed_outside_delta": args.max_outside_delta,
                    "allowed_boundary_delta": args.max_boundary_delta,
                }
                pairs.append(item)
                if outside_delta > args.max_outside_delta or boundary_delta > args.max_boundary_delta:
                    violations.append(index + 1)
            finally:
                frame.close()

        report = {
            "schema": "easygif/composite-validation-v1",
            "base": str(args.base),
            "frames": len(paths),
            "size": list(base.size),
            "region": region_description,
            "ring_radius": args.ring_radius,
            "pairs": pairs,
            "violations": violations,
            "seam_risk": bool(violations),
            "passed": not violations,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if violations:
            raise SystemExit(1)
    finally:
        if approved is not None:
            approved.close()
        base.close()


if __name__ == "__main__":
    main()
