"""Basic media validation for generated assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect-width", type=int)
    parser.add_argument("--expect-height", type=int)
    parser.add_argument("--expect-frames", type=int)
    parser.add_argument("--min-frames", type=int)
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--expect-format", choices=["GIF", "WEBP", "PNG", "JPEG"])
    parser.add_argument("--source-width", type=int)
    parser.add_argument("--source-height", type=int)
    parser.add_argument("--aspect-tolerance", type=float, default=0.02)
    parser.add_argument("--require-alpha", action="store_true")
    parser.add_argument("--require-loop", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    errors = []
    report = {
        "path": str(args.path),
        "bytes": args.path.stat().st_size if args.path.is_file() else None,
    }
    try:
        with Image.open(args.path) as image:
            image.load()
            width, height = image.size
            frames = getattr(image, "n_frames", 1)
            format_name = image.format or args.path.suffix.lstrip(".").upper()
            alpha = "A" in image.getbands() or image.info.get("transparency") is not None
            loop = image.info.get("loop")
            report.update({
                "format": format_name,
                "size": [width, height],
                "frames": frames,
                "alpha": alpha,
                "loop": loop,
            })
            if args.expect_width is not None and width != args.expect_width:
                errors.append(f"width {width} != {args.expect_width}")
            if args.expect_height is not None and height != args.expect_height:
                errors.append(f"height {height} != {args.expect_height}")
            if args.expect_frames is not None and frames != args.expect_frames:
                errors.append(f"frames {frames} != {args.expect_frames}")
            if args.min_frames is not None and frames < args.min_frames:
                errors.append(f"frames {frames} < {args.min_frames}")
            if args.max_frames is not None and frames > args.max_frames:
                errors.append(f"frames {frames} > {args.max_frames}")
            if args.expect_format and format_name != args.expect_format:
                errors.append(f"format {format_name} != {args.expect_format}")
            if args.max_bytes is not None and report["bytes"] > args.max_bytes:
                errors.append(f"bytes {report['bytes']} > {args.max_bytes}")
            if args.require_alpha and not alpha:
                errors.append("alpha channel required")
            if args.require_loop and loop is None:
                errors.append("loop metadata required")
            if args.source_width and args.source_height:
                if args.source_width <= 0 or args.source_height <= 0 or args.aspect_tolerance < 0:
                    errors.append("source dimensions and aspect tolerance must be valid")
                else:
                    expected = args.source_width / args.source_height
                    actual = width / height
                    aspect_error = abs(actual / expected - 1.0)
                    report.update({
                        "source_aspect": round(expected, 6),
                        "output_aspect": round(actual, 6),
                        "aspect_relative_error": round(aspect_error, 6),
                    })
                    if aspect_error > args.aspect_tolerance:
                        errors.append(
                            f"output aspect error {aspect_error:.4f} > {args.aspect_tolerance:.4f}"
                        )
    except Exception as exc:
        errors.append(str(exc))
    report["errors"] = errors
    report["passed"] = not errors
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if errors:
            raise SystemExit(1)
        return
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        raise SystemExit(1)
    print(f"OK: {args.path}")


if __name__ == "__main__":
    main()
