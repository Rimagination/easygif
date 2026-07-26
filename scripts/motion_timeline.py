"""Create a generic motion timeline for keyframe planning."""
from __future__ import annotations

import argparse
import json


DEFAULT_BEATS = ["rest", "anticipation", "action", "peak", "hold", "return", "rest"]

PHASE_WEIGHTS = {
    "rest": 2.0,
    "hold": 1.6,
    "anticipation": 1.0,
    "action": 1.2,
    "peak": 1.0,
    "return": 1.4,
    "settle": 1.3,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=9)
    parser.add_argument("--fps", type=float, default=8)
    parser.add_argument("--beats", default=",".join(DEFAULT_BEATS))
    parser.add_argument("--primary", default="unspecified target")
    parser.add_argument("--scope", default="local")
    parser.add_argument("--family", default="mixed")
    parser.add_argument("--equal-spacing", action="store_true", help="retain the legacy equal-beat timing")
    args = parser.parse_args()
    if args.frames < 2 or args.fps <= 0:
        raise SystemExit("frames must be at least 2 and fps must be positive")
    beats = [beat.strip() for beat in args.beats.split(",") if beat.strip()]
    if len(beats) < 2:
        raise SystemExit("at least two timeline beats are required")
    weights = [1.0 if args.equal_spacing else PHASE_WEIGHTS.get(beat.lower(), 1.0) for beat in beats]
    cumulative = []
    total_weight = sum(weights)
    running = 0.0
    for weight in weights:
        running += weight
        cumulative.append(running)
    timeline = []
    for index in range(args.frames):
        position = index / (args.frames - 1)
        target = position * total_weight
        beat_index = next((item for item, end in enumerate(cumulative) if target <= end), len(beats) - 1)
        timeline.append({
            "frame": index,
            "time_ms": round(index * 1000 / args.fps),
            "beat": beats[beat_index],
            "normalized_time": round(position, 4),
            "phase_weight": weights[beat_index],
        })
    print(json.dumps({
        "scope": args.scope,
        "family": args.family,
        "primary_target": args.primary,
        "fps": args.fps,
        "spacing": "equal" if args.equal_spacing else "phase-weighted",
        "frames": timeline,
        "loop": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
