"""Compile a user-visible production card before generation or encoding."""
from __future__ import annotations

import argparse
import json
from argparse import Namespace

from motion_recipe import RECIPES
from select_strategy import choose


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", default="short looping visual asset")
    parser.add_argument("--subject", default="the focal subject from the reference image")
    parser.add_argument("--action", default="one readable low-amplitude motion inferred from the image")
    parser.add_argument("--micro", action="append", default=[])
    parser.add_argument("--family", choices=sorted(RECIPES), default="mixed")
    parser.add_argument("--scope", choices=["local", "cluster", "global", "scene"], default="local")
    parser.add_argument("--continuity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--input-source", choices=["still", "keyframes", "video"], default="still")
    parser.add_argument(
        "--reference-source",
        choices=["user-provided", "generated", "video-first-frame"],
        default="generated",
    )
    parser.add_argument(
        "--reference-confidence",
        choices=["high", "medium", "low"],
        default="medium",
        help="How confidently one canonical reference can be selected without user review",
    )
    parser.add_argument(
        "--reference-status",
        choices=["auto", "locked", "needs-user-selection"],
        default="auto",
    )
    parser.add_argument("--source-width", type=int, required=True)
    parser.add_argument("--source-height", type=int, required=True)
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--platform-profile")
    parser.add_argument("--target-format", choices=["auto", "gif", "webp", "mp4", "sprite", "frames"], default="auto")
    parser.add_argument("--max-bytes", type=int, default=0)
    parser.add_argument("--preserve-alpha", action="store_true")
    parser.add_argument("--trusted-region", action="store_true")
    parser.add_argument("--alpha-patch", action="store_true")
    parser.add_argument("--parametric-patch", action="store_true")
    parser.add_argument("--lock", action="append", default=[])
    parser.add_argument("--avoid", action="append", default=[])
    args = parser.parse_args()
    if args.frames < 0 or args.max_bytes < 0:
        raise SystemExit("frames and max-bytes must be non-negative")

    route = choose(Namespace(
        preserve_alpha=args.preserve_alpha,
        input_source=args.input_source,
        scope=args.scope,
        family=args.family,
        continuity=args.continuity,
        frames=args.frames,
        source_width=args.source_width,
        source_height=args.source_height,
        atlas_width=1536,
        atlas_height=None,
        grid_role="auto",
        max_grid_cells=0,
        max_grid_side=0,
        target_format=args.target_format,
        max_bytes=args.max_bytes,
        trusted_region=args.trusted_region,
        alpha_patch=args.alpha_patch,
        parametric_patch=args.parametric_patch,
        platform_profile=args.platform_profile,
    ))
    if args.reference_status != "auto":
        reference_status = args.reference_status
    elif args.reference_source in {"user-provided", "video-first-frame"}:
        reference_status = "locked"
    elif args.reference_confidence == "low":
        reference_status = "needs-user-selection"
    else:
        reference_status = "locked"
    defaults = RECIPES[args.family]
    micro = args.micro or defaults["micro"][:1]
    locked = args.lock or [
        "subject identity and topology",
        "camera, framing, and background",
        "visual medium, linework, and lighting",
        "source aspect ratio",
    ]
    avoid = args.avoid or defaults["avoid"]
    result = {
        "schema": "easygif/preflight-v1",
        "status": "ready_for_execution" if reference_status == "locked" else "needs_user_selection",
        "goal": args.goal,
        "subject": args.subject,
        "input_source": args.input_source,
        "reference": {
            "source": args.reference_source,
            "status": reference_status,
            "confidence": args.reference_confidence,
            "canonical_policy": "lock one still reference and reuse it for every generated frame or keyframe",
            "selection_action": (
                "use the supplied reference directly"
                if args.reference_source == "user-provided"
                else "select a representative first frame before animation"
                if args.reference_source == "video-first-frame"
                else "generate one canonical still first; show 2-3 candidates when confidence is low"
            ),
        },
        "primary_motion": args.action,
        "micro_motions": micro[:2],
        "locked_invariants": locked,
        "representation": route["composition_contract"]["mode"],
        "generation_plan": {
            "frames": route["grid_plan"]["effective_frames"],
            "grid": route["grid_plan"],
            "strategy": route["strategy"],
        },
        "playback_plan": {
            "recommended_fps": route["recommended_fps"],
            "loop": "return to the first rest pose",
            "timing": ["rest", "anticipation", "action", "peak", "return", "settle"],
        },
        "delivery_contract": route["platform_contract"],
        "risks_and_avoid": avoid,
        "validation_gates": route["validators"],
        "route": route,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
