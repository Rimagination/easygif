"""Convert an existing video into a compact, looping GIF for chat use."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def probe_dimensions(ffprobe: str, path: Path) -> tuple[int, int]:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() if exc.stderr else "unknown ffprobe error"
        raise SystemExit(f"could not read video dimensions: {detail}") from exc
    raw = result.stdout.strip()
    try:
        width, height = (int(value) for value in raw.split("x", 1))
    except (ValueError, TypeError):
        raise SystemExit(f"could not read video dimensions from ffprobe: {raw!r}")
    if width <= 0 or height <= 0:
        raise SystemExit(f"invalid video dimensions: {width}x{height}")
    return width, height


def aspect_preserving_size(source_size: tuple[int, int], long_edge: int) -> tuple[int, int]:
    width, height = source_size
    scale = long_edge / max(width, height)
    return max(16, round(width * scale)), max(16, round(height * scale))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float, default=8)
    parser.add_argument("--size", type=int, default=240)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--square", action="store_true", help="force a square canvas; otherwise --size preserves the source aspect ratio")
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
    if (args.width is None) != (args.height is None):
        raise SystemExit("--width and --height must be supplied together")
    if args.width is not None and args.height is not None:
        width, height = args.width, args.height
    elif args.square:
        width, height = args.size, args.size
    else:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise SystemExit("ffprobe is required to preserve video aspect ratio; pass --square to avoid probing")
        width, height = aspect_preserving_size(probe_dimensions(ffprobe, args.input), args.size)
    if args.size < 16 or args.fps <= 0 or min(width, height) < 16:
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
