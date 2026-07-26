"""Resize, palette-optimize, and budget-check an animated GIF."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageOps


def parse_background(value: str, sample: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if value == "auto":
        return sample
    if value == "transparent":
        return (0, 0, 0, 0)
    raw = value.lstrip("#")
    if len(raw) not in {6, 8}:
        raise SystemExit("background must be auto, transparent, RRGGBB, or RRGGBBAA")
    values = tuple(int(raw[index:index + 2], 16) for index in range(0, len(raw), 2))
    return values if len(values) == 4 else (*values, 255)


def fit_frame(frame: Image.Image, size: tuple[int, int], mode: str, background: str) -> Image.Image:
    if mode == "stretch":
        return frame.resize(size, Image.Resampling.LANCZOS)
    fitted = ImageOps.contain(frame, size, method=Image.Resampling.LANCZOS)
    sample = frame.getpixel((0, 0))
    canvas = Image.new("RGBA", size, parse_background(background, sample))
    canvas.alpha_composite(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    fitted.close()
    return canvas


def sample_indices(total: int, requested: int) -> list[int]:
    if requested >= total:
        return list(range(total))
    if requested < 2:
        return [0]
    result = []
    for index in range(requested):
        value = round(index * (total - 1) / (requested - 1))
        if not result or result[-1] != value:
            result.append(value)
    return result


def encode_gif(
    source_frames: list[Image.Image],
    source_durations: list[int],
    indices: list[int],
    output: Path,
    size: tuple[int, int],
    colors: int,
    fit: str,
    background: str,
) -> None:
    frames = []
    durations = []
    try:
        for position, index in enumerate(indices):
            converted = fit_frame(source_frames[index], size, fit, background)
            frames.append(converted.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors))
            converted.close()
            next_index = indices[position + 1] if position + 1 < len(indices) else len(source_frames)
            durations.append(max(1, sum(source_durations[index:next_index])))
        frames[0].save(
            output,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=2,
            format="GIF",
        )
    finally:
        for frame in frames:
            frame.close()


def size_candidates(initial: tuple[int, int], minimum: int) -> list[tuple[int, int]]:
    result = [initial]
    long_edge = max(initial)
    short_edge = min(initial)
    for factor in (0.90, 0.80, 0.70, 0.60, 0.50):
        long_value = max(minimum, round(long_edge * factor))
        short_value = max(minimum, round(short_edge * factor))
        candidate = (long_value, short_value) if initial[0] >= initial[1] else (short_value, long_value)
        if candidate not in result:
            result.append(candidate)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=240)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--colors", type=int, default=128)
    parser.add_argument("--fit", choices=["contain", "stretch"], default="contain")
    parser.add_argument("--background", default="auto", help="contain fill: auto, transparent, RRGGBB, or RRGGBBAA")
    parser.add_argument("--max-bytes", type=int, help="retry colors, dimensions, and frame count until this budget is met")
    parser.add_argument("--min-colors", type=int, choices=[32, 64, 128, 256], default=32)
    parser.add_argument("--min-size", type=int, default=64)
    parser.add_argument("--min-frames", type=int, default=2)
    parser.add_argument("--preserve-size", action="store_true", help="do not reduce dimensions for a byte budget")
    args = parser.parse_args()
    if args.size < 16 or args.colors not in {32, 64, 128, 256}:
        raise SystemExit("size must be >= 16 and colors must be 32, 64, 128, or 256")
    if args.min_colors > args.colors:
        raise SystemExit("min-colors cannot exceed colors")
    if args.min_size < 16 or args.min_frames < 2:
        raise SystemExit("min-size must be >= 16 and min-frames must be at least 2")
    if args.max_bytes is not None and args.max_bytes <= 0:
        raise SystemExit("max-bytes must be positive")
    if not args.input.is_file():
        raise SystemExit(f"input GIF not found: {args.input}")

    source_frames: list[Image.Image] = []
    source_durations: list[int] = []
    with Image.open(args.input) as source:
        for index in range(getattr(source, "n_frames", 1)):
            source.seek(index)
            source_frames.append(source.convert("RGBA"))
            source_durations.append(max(1, int(source.info.get("duration", 100))))

    initial = (args.width or args.size, args.height or args.size)
    if min(initial) < 16:
        raise SystemExit("width and height must be at least 16")
    size_options = [initial] if args.preserve_size or args.max_bytes is None else size_candidates(initial, args.min_size)
    color_options = [args.colors]
    if args.max_bytes is not None:
        color_options += [value for value in (128, 64, 32) if value < args.colors and value >= args.min_colors]
    frame_options = [len(source_frames)]
    if args.max_bytes is not None:
        frame_options += [
            count for count in (max(args.min_frames, math.ceil(len(source_frames) * 0.75)), max(args.min_frames, math.ceil(len(source_frames) * 0.5)))
            if args.min_frames <= count < len(source_frames)
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    best_size = None
    accepted = False
    try:
        for frame_count in frame_options:
            indices = sample_indices(len(source_frames), frame_count)
            for size in size_options:
                for colors in color_options:
                    encode_gif(source_frames, source_durations, indices, temporary, size, colors, args.fit, args.background)
                    actual_size = temporary.stat().st_size
                    best_size = (actual_size, size, colors, len(indices))
                    if args.max_bytes is None or actual_size <= args.max_bytes:
                        temporary.replace(args.output)
                        accepted = True
                        break
                if accepted:
                    break
            if accepted:
                break
        if not accepted:
            if best_size is None:
                raise SystemExit("failed to encode GIF")
            temporary.replace(args.output)
            raise SystemExit(
                f"could not meet max-bytes={args.max_bytes}; smallest candidate is {best_size[0]} bytes "
                f"at {best_size[1][0]}x{best_size[1][1]}, {best_size[2]} colors, {best_size[3]} frames"
            )
    finally:
        if temporary.exists():
            temporary.unlink()
        for frame in source_frames:
            frame.close()
    print(f"wrote {best_size[3] if best_size else len(source_frames)} frames to {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
