"""Create and check a canonical reference contract for animation frames."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_LOCKS = [
    "subject identity and topology",
    "camera, framing, and crop",
    "background and scene layout",
    "lighting direction and visual medium",
    "source aspect ratio",
]


def describe(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"reference not found: {path}")
    with Image.open(path) as image:
        image.load()
        return {
            "path": str(path),
            "format": image.format,
            "size": list(image.size),
            "aspect_ratio": round(image.width / image.height, 6),
            "alpha": "A" in image.getbands(),
        }


def check(reference: dict[str, Any], candidate: Path, tolerance: float) -> dict[str, Any]:
    current = describe(candidate)
    errors: list[str] = []
    ref_size = reference["size"]
    if current["size"] != ref_size:
        errors.append(f"size {current['size']} != reference {ref_size}")
    aspect_error = abs(current["aspect_ratio"] / reference["aspect_ratio"] - 1.0)
    if aspect_error > tolerance:
        errors.append(f"aspect error {aspect_error:.6f} > {tolerance:.6f}")
    if reference.get("alpha") and not current.get("alpha"):
        errors.append("reference has alpha but candidate does not")
    return {"candidate": current, "aspect_error": round(aspect_error, 6), "errors": errors, "passed": not errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-kind",
        choices=["user-provided", "generated", "video-first-frame"],
        default="user-provided",
    )
    parser.add_argument(
        "--status",
        choices=["locked", "needs-user-selection"],
        default="locked",
    )
    parser.add_argument("--lock", action="append", default=[])
    parser.add_argument("--candidate", type=Path, action="append", default=[])
    parser.add_argument("--aspect-tolerance", type=float, default=0.02)
    args = parser.parse_args()
    if args.aspect_tolerance < 0:
        raise SystemExit("aspect-tolerance must be non-negative")
    reference = describe(args.reference)
    report = {
        "schema": "easygif/reference-lock-v1",
        "source_kind": args.source_kind,
        "status": args.status,
        "approval": "manual" if args.source_kind == "user-provided" else "auto-or-user-selected",
        "reference": reference,
        "locked_invariants": list(dict.fromkeys(DEFAULT_LOCKS + args.lock)),
        "candidate_checks": [check(reference, path, args.aspect_tolerance) for path in args.candidate],
        "limitations": [
            "This contract checks structural invariants such as size, aspect, and alpha; it does not prove semantic identity.",
            "Use the reference and locked_invariants in every generation prompt and review the contact sheet visually.",
        ],
    }
    report["passed"] = all(item["passed"] for item in report["candidate_checks"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
