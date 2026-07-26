"""Interpolate ordered RGB keyframes with the locally installed FILM model.

Run this script with the dedicated FILM Python environment.  It deliberately
does not import TensorFlow until execution, so the main skill environment stays
lightweight.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames", type=Path, help="ordered keyframe directory")
    parser.add_argument("output", type=Path, help="output interpolated frame directory")
    parser.add_argument("--model", type=Path, required=True, help="FILM SavedModel directory")
    parser.add_argument("--film-repo", type=Path, required=True, help="cloned frame-interpolation repository")
    parser.add_argument("--times", type=int, default=1, help="recursive midpoint passes; 1 adds one frame between each pair")
    parser.add_argument("--align", type=int, default=64, help="pad inputs to this alignment before inference")
    parser.add_argument("--block-height", type=int, default=1)
    parser.add_argument("--block-width", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.times < 1:
        raise SystemExit("--times must be at least 1")
    if not args.model.is_dir():
        raise SystemExit(f"FILM model directory not found: {args.model}")
    if not args.film_repo.is_dir():
        raise SystemExit(f"FILM repository not found: {args.film_repo}")

    paths = sorted(
        path for path in args.frames.iterdir()
        if path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if len(paths) < 2:
        raise SystemExit("at least two keyframes are required")

    sizes = set()
    has_alpha = False
    for path in paths:
        with Image.open(path) as image:
            sizes.add(image.size)
            has_alpha = has_alpha or "A" in image.getbands()
    if len(sizes) != 1:
        raise SystemExit("all keyframes must have the same dimensions")
    if has_alpha:
        raise SystemExit("FILM interpolation expects opaque RGB frames; preserve alpha with the grid pipeline")

    sys.path.insert(0, str(args.film_repo.resolve()))
    from eval import interpolator as interpolator_lib  # type: ignore[import-not-found]
    from eval import util  # type: ignore[import-not-found]

    interpolator = interpolator_lib.Interpolator(
        str(args.model),
        args.align,
        [args.block_height, args.block_width],
    )
    generated = util.interpolate_recursively_from_files(
        [str(path) for path in paths], args.times, interpolator
    )

    args.output.mkdir(parents=True, exist_ok=True)
    old_frames = list(args.output.glob("frame-*.png"))
    for old_frame in old_frames:
        old_frame.unlink()
    count = 0
    for frame in generated:
        util.write_image(str(args.output / f"frame-{count:03d}.png"), frame)
        count += 1
    print(f"wrote {count} FILM frames to {args.output}")


if __name__ == "__main__":
    main()
