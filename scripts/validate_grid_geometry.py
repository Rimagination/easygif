"""Validate atlas divisibility and cell aspect before slicing a generated grid."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def relative_error(actual: float, expected: float) -> float:
    return abs(actual / expected - 1.0)


def inspect_atlas(
    atlas: Path,
    rows: int,
    cols: int,
    expected_cell_aspect: float,
    tolerance: float = 0.08,
) -> dict[str, object]:
    """Return a geometry report without exiting the host process."""
    if rows < 1 or cols < 1 or tolerance < 0:
        raise ValueError("rows, cols, and tolerance must be valid positive values")
    if expected_cell_aspect <= 0:
        raise ValueError("expected cell aspect must be positive")
    with Image.open(atlas) as image:
        width, height = image.size
    divisible = width % cols == 0 and height % rows == 0
    report: dict[str, object] = {
        "atlas": str(atlas),
        "size": [width, height],
        "rows": rows,
        "cols": cols,
        "divisible": divisible,
    }
    if not divisible:
        report.update({"passed": False, "reason": "atlas dimensions are not divisible by rows and cols"})
        return report

    cell_width, cell_height = width // cols, height // rows
    actual_cell_aspect = cell_width / cell_height
    expected_atlas_aspect = expected_cell_aspect * cols / rows
    actual_atlas_aspect = width / height
    cell_error = relative_error(actual_cell_aspect, expected_cell_aspect)
    atlas_error = relative_error(actual_atlas_aspect, expected_atlas_aspect)
    passed = cell_error <= tolerance and atlas_error <= tolerance
    report.update({
        "cell_size": [cell_width, cell_height],
        "actual_cell_aspect": round(actual_cell_aspect, 6),
        "expected_cell_aspect": round(expected_cell_aspect, 6),
        "actual_atlas_aspect": round(actual_atlas_aspect, 6),
        "expected_atlas_aspect": round(expected_atlas_aspect, 6),
        "cell_relative_error": round(cell_error, 6),
        "atlas_relative_error": round(atlas_error, 6),
        "tolerance": tolerance,
        "passed": passed,
    })
    if not passed:
        report["reason"] = "cell or atlas aspect differs from the planned source geometry"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reject a contact sheet whose actual cell or atlas aspect differs from the planned geometry."
    )
    parser.add_argument("atlas", type=Path)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    parser.add_argument("--source-width", type=int)
    parser.add_argument("--source-height", type=int)
    parser.add_argument("--expected-cell-aspect", type=float)
    parser.add_argument("--tolerance", type=float, default=0.08)
    args = parser.parse_args()
    if args.rows < 1 or args.cols < 1 or args.tolerance < 0:
        raise SystemExit("rows, cols, and tolerance must be valid positive values")
    if args.expected_cell_aspect is None and (not args.source_width or not args.source_height):
        raise SystemExit("provide --expected-cell-aspect or both source dimensions")
    if args.expected_cell_aspect is None:
        if args.source_width <= 0 or args.source_height <= 0:
            raise SystemExit("source dimensions must be positive")
        expected_cell_aspect = args.source_width / args.source_height
    else:
        expected_cell_aspect = args.expected_cell_aspect
    if expected_cell_aspect <= 0:
        raise SystemExit("expected cell aspect must be positive")

    report = inspect_atlas(args.atlas, args.rows, args.cols, expected_cell_aspect, args.tolerance)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
