"""Choose a media-generation route from capability axes, not scene labels."""
from __future__ import annotations

import argparse
import json

from grid_plan import recommend
from sticker_package import load_profile


BACKENDS = {
    "alpha_safe_layers": ["imagegen_contact_sheet", "local_rgba_composite", "pillow_or_gifski"],
    "video_extract": ["ffmpeg_extract", "pillow_or_gifski"],
    "parametric_or_local_layers": ["local_rgba_composite", "pillow_or_gifski"],
    "local_keyframes_then_interpolation": ["keyframe_generator", "film_opaque_crop", "pillow_or_gifski"],
    "full_keyframes_then_interpolation": ["keyframe_generator", "film_opaque", "pillow_or_gifski"],
    "keyframes_then_interpolation": ["keyframe_generator", "film_opaque", "pillow_or_gifski"],
    "contact_sheet": ["imagegen_contact_sheet", "validated_grid_slice", "pillow_or_gifski"],
}


FALLBACKS = {
    "alpha_safe_layers": ["validated_contact_sheet", "independent_alpha_safe_frames"],
    "video_extract": ["keyframes_then_interpolation", "contact_sheet"],
    "parametric_or_local_layers": ["local_keyframes_then_interpolation", "contact_sheet"],
    "local_keyframes_then_interpolation": ["full_keyframes_then_interpolation", "contact_sheet"],
    "full_keyframes_then_interpolation": ["contact_sheet", "video_source"],
    "keyframes_then_interpolation": ["contact_sheet", "video_source"],
    "contact_sheet": ["independent_keyframes", "full_keyframes_then_interpolation"],
}


LAYER_STRATEGIES = {
    "alpha_safe_layers",
    "parametric_or_local_layers",
}


def choose(args: argparse.Namespace) -> dict[str, object]:
    explicit_layer_source = any(
        getattr(args, name, False)
        for name in ("trusted_region", "alpha_patch", "parametric_patch")
    )
    if args.preserve_alpha:
        strategy = "alpha_safe_layers"
        reason = "preserve alpha with layered or mask-based compositing"
    elif args.input_source == "video":
        strategy = "video_extract"
        reason = "an existing video is the strongest temporal source"
    elif args.scope == "local" and args.family in {"transform", "appearance", "periodic"} and explicit_layer_source:
        strategy = "parametric_or_local_layers"
        reason = "an explicit trusted region, alpha patch, or parametric patch can preserve the static base"
    elif args.scope in {"local", "cluster"} and args.family in {"transform", "appearance", "periodic"}:
        strategy = "local_keyframes_then_interpolation" if args.continuity == "high" else "contact_sheet"
        reason = "the motion is semantically local but no trusted pixel region was supplied; keep generated frames whole"
    elif args.scope in {"local", "cluster"} and args.continuity == "high":
        strategy = "local_keyframes_then_interpolation"
        reason = "high continuity is safer when interpolation is restricted to the moving region"
    elif args.family in {"articulated", "deformable", "relational", "mixed"} or args.continuity == "high":
        strategy = "full_keyframes_then_interpolation"
        reason = "structured or continuous motion needs explicit keyframe planning"
    elif args.frames > 16:
        strategy = "keyframes_then_interpolation"
        reason = "many frames are more reliable as planned keyframes than one contact sheet"
    else:
        strategy = "contact_sheet"
        reason = "low continuity and few frames make a validated contact sheet sufficient"
    if args.grid_role == "auto":
        grid_role = "generation" if strategy == "contact_sheet" or args.input_source == "still" else "packaging"
    else:
        grid_role = args.grid_role
    uses_layer_compositing = (
        strategy in LAYER_STRATEGIES
        or (strategy == "local_keyframes_then_interpolation" and explicit_layer_source)
    )
    grid = recommend(
        requested_frames=args.frames or None,
        scope=args.scope,
        family=args.family,
        continuity=args.continuity,
        source_width=args.source_width,
        source_height=args.source_height,
        atlas_width=args.atlas_width,
        atlas_height=args.atlas_height,
        role=grid_role,
        max_cells=args.max_grid_cells,
        max_grid_side=args.max_grid_side,
    )
    profile = load_profile(args.platform_profile) if getattr(args, "platform_profile", None) else None
    profile_max_bytes = (profile.get("main", {}).get("max_bytes") if profile else None) or 0
    effective_max_bytes = args.max_bytes or profile_max_bytes
    target_format = args.target_format
    if target_format == "auto":
        target_format = "gif" if effective_max_bytes else "webp_or_mp4"
    validators = ["validate_output", "temporal_validate"]
    if grid_role == "generation" or strategy == "contact_sheet":
        validators.insert(0, "validate_grid_geometry")
    if uses_layer_compositing:
        validators.extend(["region_validate", "composite_validate"])
    validators.append("media_budget")
    region_repair_policy = (
        "repair_trusted_mask_or_patch; never use approximate color extraction"
        if uses_layer_compositing
        else "treat as full_frame_drift; regenerate full frames and do not split the subject from the background"
    )
    return {
        "plan_version": "easygif/route-v1",
        "strategy": strategy,
        "representation": strategy.replace("_", " "),
        "reason": reason,
        "recommended_fps": 8 if "interpolation" in strategy or strategy == "video_extract" else 6,
        "preserve_aspect_ratio": True,
        "film_allowed": "interpolation" in strategy,
        "preserve_static_base": uses_layer_compositing,
        "requires_region_validation": uses_layer_compositing,
        "composition_contract": {
            "mode": "static_base_plus_patch" if uses_layer_compositing else "full_frame",
            "mask_policy": (
                "explicit_alpha_or_validated_mask_only"
                if uses_layer_compositing
                else "do_not_split_generated_full_frames"
            ),
            "seam_policy": "reject_unvalidated_cutout_edges_and_outside_region_drift",
            "full_frame_region_check": "diagnostic_only",
        },
        "grid_primary": strategy == "contact_sheet",
        "grid_role": grid_role,
        "target_format": target_format,
        "platform_profile": profile.get("id") if profile else None,
        "platform_contract": {
            "formats": profile.get("main", {}).get("formats", []) if profile else [],
            "width": profile.get("main", {}).get("width") if profile else None,
            "height": profile.get("main", {}).get("height") if profile else None,
            "max_bytes": effective_max_bytes or None,
            "aspect_policy": profile.get("main", {}).get("aspect_policy") if profile else "preserve",
        },
        "layer_source": {
            "explicit": explicit_layer_source,
            "required_for_layer_route": True,
            "flags": [name for name in ("trusted_region", "alpha_patch", "parametric_patch") if getattr(args, name, False)],
        },
        "backend_candidates": BACKENDS[strategy],
        "fallbacks": FALLBACKS[strategy],
        "validators": validators,
        "backend_resolution": "run scripts/probe_backends.py before execution and remove unavailable optional backends",
        "repair_policy": {
            "geometry": "regenerate_or_replan; never crop_or_stretch_as_repair",
            "temporal": "repair keyframe phases or reduce motion; do not blindly increase interpolation",
            "region": region_repair_policy,
            "budget": "reduce colors, then dimensions, then playback frames",
        },
        "grid_plan": grid,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="unspecified")
    parser.add_argument("--scope", choices=["local", "cluster", "global", "scene"], default="local")
    parser.add_argument("--family", choices=["transform", "articulated", "deformable", "periodic", "appearance", "camera", "environmental", "relational", "mixed"], default="mixed")
    parser.add_argument("--continuity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--input-source", choices=["still", "keyframes", "video"], default="still")
    parser.add_argument("--preserve-alpha", action="store_true")
    parser.add_argument("--motion", choices=["idle", "expression", "narrative", "camera", "fast"])
    parser.add_argument("--complexity", choices=["simple", "complex", "cinematic"])
    parser.add_argument("--frames", type=int, default=0, help="soft requested frame count; 0 infers it")
    parser.add_argument("--source-width", type=int, default=1)
    parser.add_argument("--source-height", type=int, default=1)
    parser.add_argument("--atlas-width", type=int, default=1536)
    parser.add_argument("--atlas-height", type=int)
    parser.add_argument("--grid-role", choices=["auto", "generation", "packaging"], default="auto")
    parser.add_argument("--max-grid-cells", type=int, default=0)
    parser.add_argument("--max-grid-side", type=int, default=0)
    parser.add_argument("--target-format", choices=["auto", "gif", "webp", "mp4", "sprite", "frames"], default="auto")
    parser.add_argument("--max-bytes", type=int, default=0)
    parser.add_argument("--has-video", action="store_true")
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--trusted-region", action="store_true", help="an explicit validated region or mask is available")
    parser.add_argument("--alpha-patch", action="store_true", help="ordered RGBA patches are available")
    parser.add_argument("--parametric-patch", action="store_true", help="a deterministic local transform is available")
    parser.add_argument("--platform-profile", help="built-in profile name or JSON path, e.g. wechat-chat")
    args = parser.parse_args()
    if args.has_video:
        args.input_source = "video"
    if args.transparent:
        args.preserve_alpha = True
    if args.motion in {"narrative", "camera", "fast"} or args.complexity in {"complex", "cinematic"}:
        args.continuity = "high"
    if args.motion == "camera":
        args.scope = "scene"
    if args.frames < 0:
        raise SystemExit("frames must be non-negative")
    if args.max_bytes < 0:
        raise SystemExit("max-bytes must be non-negative")
    print(json.dumps(choose(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
