"""Crop a fixed atlas and assemble it into a looping GIF or animated WebP."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

try:
    from validate_grid_geometry import inspect_atlas
except ImportError:  # pragma: no cover - supports package-style imports
    from .validate_grid_geometry import inspect_atlas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("atlas", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    parser.add_argument("--fps", type=float, default=12)
    parser.add_argument("--loop", type=int, default=0)
    parser.add_argument("--frames", type=int, help="only use the first N row-major cells")
    parser.add_argument("--source-width", type=int)
    parser.add_argument("--source-height", type=int)
    parser.add_argument("--expected-cell-aspect", type=float)
    parser.add_argument("--tolerance", type=float, default=0.08)
    args = parser.parse_args()
    if args.rows < 1 or args.cols < 1 or args.fps <= 0:
        raise SystemExit("rows, cols, and fps must be positive")
    if args.frames is not None and not 1 <= args.frames <= args.rows * args.cols:
        raise SystemExit("frames must be between 1 and rows*cols")
    if args.expected_cell_aspect is None and args.source_width and args.source_height:
        args.expected_cell_aspect = args.source_width / args.source_height

    frames = []
    with Image.open(args.atlas) as image:
        width, height = image.size
        if width % args.cols or height % args.rows:
            raise SystemExit(f"atlas {width}x{height} is not divisible by {args.cols}x{args.rows}")
        if args.expected_cell_aspect is not None:
            report = inspect_atlas(args.atlas, args.rows, args.cols, args.expected_cell_aspect, args.tolerance)
            if not report["passed"]:
                raise SystemExit("grid geometry validation failed: " + str(report.get("reason", "aspect mismatch")))
        cell_w, cell_h = width // args.cols, height // args.rows
        for row in range(args.rows):
            for col in range(args.cols):
                if args.frames is not None and len(frames) >= args.frames:
                    break
                box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
                frames.append(image.crop(box).convert("RGBA"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    duration = max(1, round(1000 / args.fps))
    if args.output.suffix.lower() == ".webp":
        frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=duration, loop=args.loop, format="WEBP", lossless=True)
    else:
        frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=duration, loop=args.loop, format="GIF", disposal=2, optimize=True)
    for frame in frames:
        frame.close()
    print(f"wrote {len(frames)} frames to {args.output}")


if __name__ == "__main__":
    main()
