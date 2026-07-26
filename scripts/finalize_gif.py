"""Turn a staged GIF into a validated, explicitly delivered GIF."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_validation(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    validator = Path(__file__).with_name("validate_output.py")
    command = [sys.executable, str(validator), str(args.output), "--json", "--require-loop"]
    command += ["--expect-format", "GIF"]
    for flag, value in (
        ("--expect-width", args.expect_width),
        ("--expect-height", args.expect_height),
        ("--expect-frames", args.expect_frames),
        ("--source-width", args.source_width),
        ("--source-height", args.source_height),
        ("--max-bytes", args.max_bytes),
    ):
        if value is not None:
            command += [flag, str(value)]
    if args.require_alpha:
        command.append("--require-alpha")
    result = subprocess.run(command, capture_output=True, text=True)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {
            "passed": False,
            "errors": [result.stdout.strip() or result.stderr.strip() or "validator returned no JSON"],
        }
    return result.returncode, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="staged source GIF; never report this as the final asset")
    parser.add_argument("output", type=Path, help="final GIF path to deliver")
    parser.add_argument("--size", type=int, default=240)
    parser.add_argument("--square", action="store_true")
    parser.add_argument("--fit", choices=["contain", "stretch"], default="contain")
    parser.add_argument("--colors", type=int, choices=[32, 64, 128, 256], default=256)
    parser.add_argument("--dither", choices=["none", "floyd-steinberg"], default="none")
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--expect-width", type=int)
    parser.add_argument("--expect-height", type=int)
    parser.add_argument("--expect-frames", type=int)
    parser.add_argument("--source-width", type=int)
    parser.add_argument("--source-height", type=int)
    parser.add_argument("--require-alpha", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"staged GIF not found: {args.input}")
    if args.input.resolve() == args.output.resolve():
        raise SystemExit("input and output must be different paths")
    if args.size < 16 or (args.max_bytes is not None and args.max_bytes <= 0):
        raise SystemExit("size must be >= 16 and max-bytes must be positive")

    optimizer = Path(__file__).with_name("optimize_gif.py")
    command = [
        sys.executable,
        str(optimizer),
        str(args.input),
        str(args.output),
        "--size",
        str(args.size),
        "--fit",
        args.fit,
        "--colors",
        str(args.colors),
        "--dither",
        args.dither,
    ]
    if args.square:
        command.append("--square")
    if args.max_bytes is not None:
        command += ["--max-bytes", str(args.max_bytes)]
    optimized = subprocess.run(command, capture_output=True, text=True)
    report: dict[str, object] = {
        "schema": "easygif/delivery-v1",
        "status": "failed" if optimized.returncode else "validating",
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "optimization": {
            "returncode": optimized.returncode,
            "stdout": optimized.stdout.strip(),
            "stderr": optimized.stderr.strip(),
            "colors": args.colors,
            "dither": args.dither,
        },
    }
    if optimized.returncode:
        report["errors"] = ["optimization failed; do not deliver the staged GIF"]
    else:
        validation_code, validation = run_validation(args)
        report["validation"] = validation
        report["status"] = "delivered" if validation_code == 0 else "validation_failed"
        if validation_code:
            report["errors"] = ["final GIF failed delivery validation"]

    target = args.report or args.output.with_name(args.output.stem + "-delivery.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "delivered":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
