"""Suggest aspect-preserving animation dimensions under a byte budget."""
from __future__ import annotations

import argparse
import json
import math


def estimate_bytes(width: int, height: int, frames: int, colors: int) -> int:
    # Conservative planning estimate. GIF compression varies with motion,
    # palette entropy, and repeated backgrounds, so the encoded file remains
    # the source of truth.
    palette_factor = 0.20 + min(colors, 256) / 512
    return round(width * height * frames * palette_factor)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, required=True, help="source or desired output width")
    parser.add_argument("--height", type=int, required=True, help="source or desired output height")
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--max-bytes", type=int, default=1_000_000)
    parser.add_argument("--colors", type=int, choices=[32, 64, 128, 256], default=128)
    parser.add_argument("--target-width", type=int)
    parser.add_argument("--target-height", type=int)
    parser.add_argument("--min-long-edge", type=int, default=64)
    args = parser.parse_args()
    if min(args.width, args.height, args.frames, args.min_long_edge) <= 0 or args.fps <= 0:
        raise SystemExit("dimensions, frames, min-long-edge, and fps must be positive")
    if args.max_bytes <= 0:
        raise SystemExit("max-bytes must be positive")
    if bool(args.target_width) != bool(args.target_height):
        raise SystemExit("target-width and target-height must be supplied together")

    aspect = args.width / args.height
    long_edges = [640, 512, 480, 400, 360, 320, 288, 240, 200, 160, 128, 96, 64]
    if args.target_width and args.target_height:
        exact_long = max(args.target_width, args.target_height)
        long_edges = [exact_long] + [edge for edge in long_edges if edge < exact_long]
    choices = []
    for long_edge in long_edges:
        if long_edge < args.min_long_edge:
            continue
        if args.width >= args.height:
            width = long_edge
            height = max(1, round(width / aspect))
        else:
            height = long_edge
            width = max(1, round(height * aspect))
        if args.target_width and args.target_height and long_edge == max(args.target_width, args.target_height):
            width, height = args.target_width, args.target_height
        estimated = estimate_bytes(width, height, args.frames, args.colors)
        choices.append({
            "width": width,
            "height": height,
            "estimated_bytes": estimated,
            "duration_ms": round(args.frames * 1000 / args.fps),
        })
    if not choices:
        raise SystemExit("no size candidate remains above min-long-edge")
    valid = [choice for choice in choices if choice["estimated_bytes"] <= args.max_bytes]
    selected = valid[0] if valid else choices[-1]
    print(json.dumps({
        "selected": selected,
        "aspect_ratio": round(aspect, 4),
        "fps": args.fps,
        "frames": args.frames,
        "max_bytes": args.max_bytes,
        "budget_met_by_estimate": bool(valid),
        "note": "heuristic only; validate the encoded GIF and reduce colors/FPS or frames if needed",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
