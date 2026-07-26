"""Assemble ordered PNG/JPEG frames into GIF or animated WebP."""
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("frames", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float, default=12)
    parser.add_argument("--loop", type=int, default=0)
    args = parser.parse_args()
    paths = sorted(p for p in args.frames.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    if not paths:
        raise SystemExit("no image frames found")
    if args.fps <= 0:
        raise SystemExit("fps must be positive")
    images = []
    try:
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert("RGBA"))
        size = images[0].size
        if any(image.size != size for image in images):
            raise SystemExit("all frames must have the same dimensions")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        duration = max(1, round(1000 / args.fps))
        if args.output.suffix.lower() == ".webp":
            images[0].save(args.output, save_all=True, append_images=images[1:], duration=duration, loop=args.loop, format="WEBP", lossless=True)
        else:
            images[0].save(args.output, save_all=True, append_images=images[1:], duration=duration, loop=args.loop, format="GIF", disposal=2, optimize=True)
    finally:
        for image in images:
            image.close()
    print(f"wrote {len(paths)} frames to {args.output}")


if __name__ == "__main__":
    main()
