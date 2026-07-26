"""Composite local RGBA patches or masked full-frame edits onto a static base."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def image_paths(path: Path) -> list[Path]:
    if not path.is_dir():
        raise SystemExit(f"expected an image directory: {path}")
    paths = sorted(item for item in path.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES)
    if not paths:
        raise SystemExit(f"no image overlays found in {path}")
    return paths


def mask_paths(path: Path | None, count: int) -> list[Path | None]:
    if path is None:
        return [None] * count
    if path.is_dir():
        paths = sorted(item for item in path.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES)
        if len(paths) != count:
            raise SystemExit("mask directory must contain exactly one mask per overlay")
        return paths
    return [path] * count


def load_mask(path: Path | None, expected_size: tuple[int, int], feather: int) -> Image.Image | None:
    if path is None:
        return None
    with Image.open(path) as source:
        mask = source.convert("L")
    if mask.size != expected_size:
        raise SystemExit(f"mask {path} has size {mask.size}, expected {expected_size}")
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    return mask


def multiply_alpha(image: Image.Image, mask: Image.Image | None) -> Image.Image:
    rgba = image.convert("RGBA")
    if mask is None:
        return rgba
    alpha = ImageChops.multiply(rgba.getchannel("A"), mask)
    rgba.putalpha(alpha)
    return rgba


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply local transparent patches or masked full-frame edits without redrawing the static base."
    )
    parser.add_argument("base", type=Path, help="static base image")
    parser.add_argument("overlays", type=Path, help="directory of ordered local patches or edits")
    parser.add_argument("output", type=Path, help="output directory for composited PNG frames")
    parser.add_argument("--mask", type=Path, help="one grayscale mask, or a directory with one mask per overlay")
    parser.add_argument("--x", type=int, default=0, help="left position for a patch smaller than the base")
    parser.add_argument("--y", type=int, default=0, help="top position for a patch smaller than the base")
    parser.add_argument("--feather", type=int, default=0, help="Gaussian blur radius for the mask edge")
    args = parser.parse_args()
    if args.x < 0 or args.y < 0 or args.feather < 0:
        raise SystemExit("x, y, and feather must be non-negative")

    with Image.open(args.base) as source:
        base = source.convert("RGBA")
    overlays = image_paths(args.overlays)
    masks = mask_paths(args.mask, len(overlays))
    args.output.mkdir(parents=True, exist_ok=True)

    try:
        for index, (overlay_path, mask_path) in enumerate(zip(overlays, masks)):
            with Image.open(overlay_path) as source:
                overlay = source.copy()
            is_full_frame = overlay.size == base.size
            if is_full_frame and (args.x or args.y):
                raise SystemExit("x/y cannot be used with a full-frame overlay")
            if not is_full_frame and (args.x + overlay.width > base.width or args.y + overlay.height > base.height):
                raise SystemExit(f"overlay {overlay_path} does not fit inside the base at x/y")

            if is_full_frame:
                local_mask = load_mask(mask_path, base.size, args.feather)
                if overlay.mode not in {"RGBA", "LA"} and local_mask is None:
                    raise SystemExit(f"full-frame overlay {overlay_path} needs alpha or --mask")
                layer = multiply_alpha(overlay, local_mask)
                result = Image.alpha_composite(base, layer)
            else:
                local_mask = load_mask(mask_path, overlay.size, args.feather)
                patch = multiply_alpha(overlay, local_mask)
                layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
                layer.alpha_composite(patch, (args.x, args.y))
                result = Image.alpha_composite(base, layer)

            result.save(args.output / f"frame-{index:03d}.png")
            overlay.close()
            result.close()
    finally:
        base.close()

    print(f"wrote {len(overlays)} composited frames to {args.output}")


if __name__ == "__main__":
    main()
