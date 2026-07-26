"""Crop a fixed grid atlas into numbered PNG frames."""
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
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    parser.add_argument("--prefix", default="frame")
    parser.add_argument("--frames", type=int, help="only emit the first N row-major frames")
    parser.add_argument("--source-width", type=int)
    parser.add_argument("--source-height", type=int)
    parser.add_argument("--expected-cell-aspect", type=float)
    parser.add_argument("--tolerance", type=float, default=0.08)
    args = parser.parse_args()
    if args.rows < 1 or args.cols < 1:
        raise SystemExit("rows and cols must be positive")
    if args.frames is not None and not 1 <= args.frames <= args.rows * args.cols:
        raise SystemExit("frames must be between 1 and rows*cols")
    if args.expected_cell_aspect is None and args.source_width and args.source_height:
        args.expected_cell_aspect = args.source_width / args.source_height

    with Image.open(args.input) as image:
        width, height = image.size
        if width % args.cols or height % args.rows:
            raise SystemExit(f"atlas {width}x{height} is not divisible by {args.cols}x{args.rows}")
        if args.expected_cell_aspect is not None:
            report = inspect_atlas(args.input, args.rows, args.cols, args.expected_cell_aspect, args.tolerance)
            if not report["passed"]:
                raise SystemExit("grid geometry validation failed: " + str(report.get("reason", "aspect mismatch")))
        cell_w, cell_h = width // args.cols, height // args.rows
        args.output.mkdir(parents=True, exist_ok=True)
        index = 0
        for row in range(args.rows):
            for col in range(args.cols):
                if args.frames is not None and index >= args.frames:
                    break
                box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
                image.crop(box).save(args.output / f"{args.prefix}-{index:03d}.png")
                index += 1
    print(f"wrote {index} frames to {args.output}")


if __name__ == "__main__":
    main()
