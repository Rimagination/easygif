"""Convert an existing video into a compact, looping GIF for chat use."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float, default=8)
    parser.add_argument("--size", type=int, default=240)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fit", choices=["contain", "stretch"], default="contain")
    parser.add_argument("--background", default="000000", help="contain padding color as RRGGBB")
    parser.add_argument("--colors", type=int, choices=[32, 64, 128, 256], default=128)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--duration", type=float)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"input video not found: {args.input}")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required for video input")
    width = args.width or args.size
    height = args.height or args.size
    if args.fps <= 0 or min(width, height) < 16:
        raise SystemExit("fps must be positive and width/height must be at least 16")
    background = args.background.lstrip("#")
    if len(background) != 6:
        raise SystemExit("background must be a six-digit RRGGBB color")

    with tempfile.TemporaryDirectory(prefix="adaptive-media-frames-") as temp:
        frame_pattern = str(Path(temp) / "frame-%06d.png")
        if args.fit == "stretch":
            vf = f"fps={args.fps},scale={width}:{height}"
        else:
            vf = (
                f"fps={args.fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x{background}"
            )
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if args.start > 0:
            command += ["-ss", str(args.start)]
        command += ["-i", str(args.input)]
        if args.duration is not None:
            command += ["-t", str(args.duration)]
        command += ["-vf", vf, "-vsync", "0", frame_pattern]
        subprocess.run(command, check=True)

        paths = sorted(Path(temp).glob("frame-*.png"))
        if not paths:
            raise SystemExit("video produced no frames")
        frames = []
        try:
            for path in paths:
                with Image.open(path) as image:
                    frame = image.convert("RGBA").convert(
                        "P", palette=Image.Palette.ADAPTIVE, colors=args.colors
                    )
                    frames.append(frame)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            duration = max(1, round(1000 / args.fps))
            frames[0].save(
                args.output,
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0,
                optimize=True,
                disposal=2,
                format="GIF",
            )
        finally:
            for frame in frames:
                frame.close()
    print(f"wrote {len(paths)} frames to {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
