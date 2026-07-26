"""Check frame continuity without assuming a particular subject or scene."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def frame_delta(left: Image.Image, right: Image.Image) -> float:
    diff = ImageChops.difference(left, right)
    return round(sum(ImageStat.Stat(diff).mean) / 3, 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames", type=Path)
    parser.add_argument("--max-spike-ratio", type=float, default=3.0)
    parser.add_argument("--check-loop", action="store_true", help="also compare the last frame with the first")
    parser.add_argument("--max-loop-ratio", type=float, default=3.0)
    args = parser.parse_args()
    if args.max_spike_ratio <= 0 or args.max_loop_ratio <= 0:
        raise SystemExit("spike ratios must be positive")
    paths = sorted(path for path in args.frames.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    if len(paths) < 2:
        raise SystemExit("at least two frames are required")
    images = []
    try:
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert("RGB"))
        sizes = {image.size for image in images}
        if len(sizes) != 1:
            raise SystemExit("all frames must have the same dimensions")
        adjacent = [frame_delta(left, right) for left, right in zip(images, images[1:])]
        loop_delta = frame_delta(images[-1], images[0]) if args.check_loop else None
        baseline = sum(adjacent) / len(adjacent)
        spikes = [
            index + 1
            for index, value in enumerate(adjacent)
            if baseline and value > baseline * args.max_spike_ratio
        ]
        loop_spike = bool(
            args.check_loop
            and baseline
            and loop_delta is not None
            and loop_delta > baseline * args.max_loop_ratio
        )
        report = {
            "frames": len(paths),
            "size": list(images[0].size),
            "mean_deltas": adjacent + ([loop_delta] if args.check_loop else []),
            "baseline_delta": round(baseline, 4),
            "spike_boundaries": spikes,
            "loop_delta": loop_delta,
            "loop_spike": loop_spike,
            "passed": not spikes and not loop_spike,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
    finally:
        for image in images:
            image.close()


if __name__ == "__main__":
    main()
