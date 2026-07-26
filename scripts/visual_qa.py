"""Create a visual contact sheet and deterministic frame QA report."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps


SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def natural_key(path: Path) -> list[object]:
    import re

    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def load_frames(source: Path) -> list[Image.Image]:
    if source.is_dir():
        paths = sorted(
            [path for path in source.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED],
            key=natural_key,
        )
        frames = []
        for path in paths:
            with Image.open(path) as image:
                image.load()
                frames.append(image.convert("RGBA"))
        return frames
    with Image.open(source) as image:
        frames = []
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            frames.append(image.convert("RGBA"))
        return frames


def difference_score(first: Image.Image, second: Image.Image) -> float:
    diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB")).convert("L")
    histogram = diff.histogram()
    total = sum(histogram)
    weighted = sum(index * count for index, count in enumerate(histogram))
    diff.close()
    return weighted / max(1, total) / 255.0


def alpha_box(frame: Image.Image) -> list[int] | None:
    alpha = frame.getchannel("A")
    box = alpha.getbbox()
    alpha.close()
    return list(box) if box else None


def build_contact_sheet(frames: list[Image.Image], output: Path, columns: int, cell_long_edge: int) -> None:
    columns = max(1, min(columns, len(frames)))
    rows = math.ceil(len(frames) / columns)
    source_w, source_h = frames[0].size
    scale = cell_long_edge / max(source_w, source_h)
    cell_w, cell_h = max(1, round(source_w * scale)), max(1, round(source_h * scale))
    label_h = 24
    canvas = Image.new("RGB", (columns * cell_w, rows * (cell_h + label_h)), (235, 235, 235))
    draw = ImageDraw.Draw(canvas)
    for index, frame in enumerate(frames):
        x = (index % columns) * cell_w
        y = (index // columns) * (cell_h + label_h)
        fitted = ImageOps.contain(frame, (cell_w, cell_h), method=Image.Resampling.LANCZOS)
        background = Image.new("RGBA", (cell_w, cell_h), (245, 245, 245, 255))
        background.alpha_composite(fitted, ((cell_w - fitted.width) // 2, (cell_h - fitted.height) // 2))
        canvas.paste(background.convert("RGB"), (x, y))
        draw.text((x + 6, y + cell_h + 4), f"frame {index:02d}", fill=(35, 35, 35))
        fitted.close()
        background.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    canvas.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="frame directory or animated image")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--columns", type=int, default=0)
    parser.add_argument("--cell-long-edge", type=int, default=256)
    parser.add_argument("--spike-factor", type=float, default=2.5)
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")
    if args.cell_long_edge < 32 or args.spike_factor <= 1:
        raise SystemExit("cell-long-edge must be >= 32 and spike-factor must be > 1")
    frames = load_frames(args.input)
    if not frames:
        raise SystemExit("no frames found")
    sizes = [list(frame.size) for frame in frames]
    errors: list[str] = []
    warnings: list[str] = []
    if len(frames) < 2:
        warnings.append("only one frame supplied; temporal continuity cannot be assessed")
    if len(set(tuple(size) for size in sizes)) != 1:
        errors.append("frame dimensions are inconsistent")
    scores = [difference_score(frames[index], frames[index + 1]) for index in range(len(frames) - 1)]
    loop_score = difference_score(frames[-1], frames[0]) if len(frames) > 1 else 0.0
    spike_boundaries: list[int] = []
    if scores:
        baseline = statistics.median(scores)
        threshold = max(0.08, baseline * args.spike_factor)
        spike_boundaries = [index + 1 for index, score in enumerate(scores) if score > threshold]
        if spike_boundaries:
            warnings.append(f"temporal spikes near boundaries {spike_boundaries}")
        if loop_score > max(0.08, baseline * args.spike_factor):
            warnings.append("loop boundary differs more than ordinary adjacent frames")
    alpha_boxes = [alpha_box(frame) for frame in frames]
    alpha_consistent = len(set(tuple(box) for box in alpha_boxes if box is not None)) <= 1
    if any(box is None for box in alpha_boxes) and any(box is not None for box in alpha_boxes):
        warnings.append("alpha occupancy changes between transparent and non-transparent frames")
    if not alpha_consistent:
        warnings.append("alpha subject bounds drift across frames")

    contact_sheet = args.contact_sheet or args.input.with_name("contact-sheet.png")
    build_contact_sheet(frames, contact_sheet, args.columns or max(1, math.ceil(math.sqrt(len(frames)))), args.cell_long_edge)
    report = {
        "schema": "easygif/visual-qa-v1",
        "input": str(args.input),
        "frames": len(frames),
        "size": sizes[0],
        "contact_sheet": str(contact_sheet),
        "temporal": {
            "adjacent_mean_difference": round(statistics.mean(scores), 6) if scores else 0.0,
            "loop_difference": round(loop_score, 6),
            "spike_boundaries": spike_boundaries,
        },
        "alpha": {
            "present": any(frame.getchannel("A").getextrema()[0] < 255 for frame in frames),
            "boxes": alpha_boxes,
            "consistent": alpha_consistent,
        },
        "errors": errors,
        "warnings": warnings,
        "passed": not errors and (not warnings or not args.fail_on_warnings),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    for frame in frames:
        frame.close()
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
