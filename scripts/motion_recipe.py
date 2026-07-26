"""Compile a conservative, object-agnostic motion recipe."""
from __future__ import annotations

import argparse
import json


RECIPES = {
    "transform": {
        "primary": "a small eased positional or rotational shift of the approved subject",
        "micro": ["subtle settle at the end of the motion"],
        "avoid": ["camera jump", "unbounded scale change"],
    },
    "articulated": {
        "primary": "one readable joint or appendage action with anticipation and return",
        "micro": ["small follow-through", "brief hold at the peak"],
        "avoid": ["independent asymmetric facial changes", "limb topology changes"],
    },
    "deformable": {
        "primary": "a restrained squash, stretch, fold, or settle of the moving form",
        "micro": ["soft volume recovery"],
        "avoid": ["rubber-like over-deformation", "new anatomy or duplicated parts"],
    },
    "periodic": {
        "primary": "a small periodic pulse, sway, blink, shimmer, or breathing cycle",
        "micro": ["phase-consistent return to the starting pose"],
        "avoid": ["single-frame pop", "uneven timing"],
    },
    "appearance": {
        "primary": "a localized change in expression, light, color, or surface response",
        "micro": ["short hold before returning to the original appearance"],
        "avoid": ["changing identity", "lighting direction reversal"],
    },
    "camera": {
        "primary": "a slow, bounded push, pan, or parallax movement with a stable subject",
        "micro": ["gentle settle before the loop closes"],
        "avoid": ["rolling camera", "perspective jump"],
    },
    "environmental": {
        "primary": "one ambient environmental movement such as a breeze, reflection, or particle drift",
        "micro": ["subtle secondary response in a nearby surface"],
        "avoid": ["moving every background object", "weather changing abruptly"],
    },
    "relational": {
        "primary": "a small interaction between the focal subject and one nearby element",
        "micro": ["reaction hold", "return to the original relationship"],
        "avoid": ["multiple simultaneous interactions", "changing scene topology"],
    },
    "mixed": {
        "primary": "one low-amplitude motion selected from the most visually supported region",
        "micro": ["one secondary micro-motion only if it reinforces the primary action"],
        "avoid": ["whole-scene redraw", "unmotivated camera movement"],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=sorted(RECIPES), default="mixed")
    parser.add_argument("--scope", choices=["local", "cluster", "global", "scene"], default="local")
    parser.add_argument("--continuity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--subject", default="focal subject")
    parser.add_argument("--region", default="smallest practical moving region")
    parser.add_argument("--user-motion", help="explicit user motion; overrides the recipe primary")
    parser.add_argument("--lock", action="append", default=[], help="element that must remain invariant")
    args = parser.parse_args()
    recipe = RECIPES[args.family]
    primary = args.user_motion or recipe["primary"]
    if args.continuity == "low":
        beats = ["rest", "action", "hold", "return", "rest"]
    elif args.continuity == "high":
        beats = ["rest", "anticipation", "action", "peak", "hold", "return", "settle", "rest"]
    else:
        beats = ["rest", "anticipation", "action", "peak", "return", "rest"]
    locked = args.lock or [
        "subject identity",
        "camera and framing",
        "background outside the approved region",
        "lighting direction and visual medium",
    ]
    print(json.dumps({
        "schema": "easygif/motion-recipe-v1",
        "subject": args.subject,
        "scope": args.scope,
        "family": args.family,
        "continuity": args.continuity,
        "primary_motion": primary,
        "micro_motions": recipe["micro"][:1 if args.continuity == "low" else 2],
        "approved_region": args.region,
        "locked_invariants": locked,
        "avoid": recipe["avoid"],
        "timeline_beats": beats,
        "loop": {"required": True, "close_with": "return to the first pose or a visually equivalent rest pose"},
        "selection_note": "The recipe is a safe starting point; inspect the image and replace the region or motion wording when evidence supports a better action.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
