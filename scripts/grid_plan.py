"""Recommend contact-sheet frame count and rows x columns geometry."""
from __future__ import annotations

import argparse
import json
import math


FAMILIES_NEEDING_MORE_BEATS = {"articulated", "deformable", "relational", "environmental", "camera"}


def inferred_frames(scope: str, family: str, continuity: str) -> int:
    frames = {"low": 4, "medium": 6, "high": 8}[continuity]
    if family in FAMILIES_NEEDING_MORE_BEATS:
        frames += 1 if continuity == "high" else 2
    if scope in {"global", "scene"} and family in {"camera", "environmental"}:
        frames += 2
    return max(4, min(16, frames))


def layouts(cell_count: int, max_grid_side: int) -> list[tuple[int, int]]:
    result = []
    for rows in range(2, min(cell_count, max_grid_side) + 1):
        if cell_count % rows:
            continue
        cols = cell_count // rows
        if 2 <= cols <= max_grid_side:
            result.append((rows, cols))
    return result


def layout_score(
    rows: int,
    cols: int,
    source_aspect: float,
    canvas_aspect: float,
) -> float:
    atlas_aspect = source_aspect * cols / rows
    aspect_error = abs(math.log(atlas_aspect / canvas_aspect))
    balance_error = abs(math.log(cols / rows))
    compact_height_penalty = rows / cols * 0.05
    return aspect_error * 3.0 + balance_error * 0.15 + compact_height_penalty


def recommend(
    requested_frames: int | None,
    scope: str,
    family: str,
    continuity: str,
    source_width: int,
    source_height: int,
    atlas_width: int,
    atlas_height: int | None,
    role: str,
    max_cells: int,
    max_grid_side: int,
) -> dict[str, object]:
    if source_width <= 0 or source_height <= 0 or atlas_width <= 0:
        raise SystemExit("source and atlas dimensions must be positive")
    if requested_frames is not None and requested_frames < 2:
        raise SystemExit("requested frames must be at least 2")
    if role not in {"generation", "packaging"}:
        raise SystemExit("role must be generation or packaging")
    if max_cells <= 0:
        max_cells = 16 if role == "generation" else 36
    if max_grid_side <= 0:
        max_grid_side = 5 if role == "generation" else 6
    if max_cells < 4 or max_grid_side < 2:
        raise SystemExit("max-cells must be at least 4 and max-grid-side at least 2")

    target = requested_frames or inferred_frames(scope, family, continuity)
    frame_count_was_capped = target > max_cells
    target = min(target, max_cells)
    source_aspect = source_width / source_height
    canvas_aspect = atlas_width / atlas_height if atlas_height else source_aspect
    candidates = []
    for cell_count in range(target, max_cells + 1):
        for rows, cols in layouts(cell_count, max_grid_side):
            atlas_aspect = source_aspect * cols / rows
            aspect_error = abs(math.log(atlas_aspect / canvas_aspect))
            score = (cell_count - target) * 4.0 + layout_score(
                rows, cols, source_aspect, canvas_aspect
            )
            candidates.append((score, cell_count, rows, cols, aspect_error))
    if not candidates:
        raise SystemExit("no usable grid found; increase max-cells or max-grid-side")

    if role == "generation":
        # Prefer a canvas-compatible grid with a small number of intentional
        # rest/hold cells. This prevents a square source from becoming a
        # portrait 2x3 atlas when the generator naturally returns a square
        # canvas. Do not add a large number of padding cells just to force a
        # perfect ratio.
        padding_limit = max(2, target // 2)
        compatible = [
            item for item in candidates
            if item[1] - target <= padding_limit and item[4] <= 0.12
        ]
        if compatible:
            candidates = compatible

    _, cell_count, rows, cols, _ = min(candidates)
    padding_frames = cell_count - target
    cell_width = atlas_width // cols
    cell_height = max(1, round(cell_width / source_aspect))
    actual_atlas = [cell_width * cols, cell_height * rows]
    min_cell_long_edge = max(cell_width, cell_height)

    if requested_frames is None:
        reason = f"inferred {target} effective frames from {family} motion with {continuity} continuity"
    else:
        reason = f"honored the requested {target} effective frames where a compact grid is available"
    if frame_count_was_capped:
        reason = f"requested {requested_frames} frames exceeds the {role} limit of {max_cells}; {reason}"
    if padding_frames:
        reason += f"; reserve {padding_frames} padding frame(s) as rest/hold poses"
    reason += f"; selected {rows}x{cols} to match source and canvas aspect"

    if role == "generation" and cell_count >= 16:
        quality_note = "4x4 is a practical upper bound for one-pass generation; if identity drifts, reduce the sheet or switch to keyframes"
    elif role == "generation" and cell_count >= 9:
        quality_note = "single-pass generation is still viable, but inspect identity and pose continuity across every cell"
    elif role == "packaging" and cell_count >= 25:
        quality_note = "dense atlas is appropriate for already-generated frames or a dedicated sprite model, not a generic one-pass image prompt"
    elif min_cell_long_edge < 256:
        quality_note = "cell detail may be limited; use independent keyframes when the moving region is too small"
    else:
        quality_note = "cell size is suitable for this representation"

    return {
        "mode": "adaptive",
        "role": role,
        "requested_frames": requested_frames,
        "effective_frames": target,
        "frame_count_was_capped": frame_count_was_capped,
        "max_cells": max_cells,
        "grid_cells": cell_count,
        "rows": rows,
        "cols": cols,
        "padding_frames": padding_frames,
        "source_aspect": round(source_aspect, 4),
        "canvas_aspect": round(canvas_aspect, 4),
        "cell_size": [cell_width, cell_height],
        "atlas_size": actual_atlas,
        "reason": reason,
        "prompt_rule": "one chronological frame per cell, row-major order, padding cells repeat rest or hold",
        "quality_note": quality_note,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose adaptive contact-sheet frame count and grid geometry.")
    parser.add_argument("--frames", type=int, default=0, help="soft requested frame count; 0 infers it")
    parser.add_argument("--scope", choices=["local", "cluster", "global", "scene"], default="local")
    parser.add_argument(
        "--family",
        choices=["transform", "articulated", "deformable", "periodic", "appearance", "camera", "environmental", "relational", "mixed"],
        default="mixed",
    )
    parser.add_argument("--continuity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--source-width", type=int, default=1)
    parser.add_argument("--source-height", type=int, default=1)
    parser.add_argument("--atlas-width", type=int, default=1536)
    parser.add_argument("--atlas-height", type=int)
    parser.add_argument("--role", choices=["generation", "packaging"], default="generation")
    parser.add_argument("--max-cells", type=int, default=0, help="0 uses 16 for generation or 36 for packaging")
    parser.add_argument("--max-grid-side", type=int, default=0, help="0 uses 5 for generation or 6 for packaging")
    args = parser.parse_args()
    print(json.dumps(recommend(
        requested_frames=args.frames or None,
        scope=args.scope,
        family=args.family,
        continuity=args.continuity,
        source_width=args.source_width,
        source_height=args.source_height,
        atlas_width=args.atlas_width,
        atlas_height=args.atlas_height,
        role=args.role,
        max_cells=args.max_cells,
        max_grid_side=args.max_grid_side,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
