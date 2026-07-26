"""Validate a packaged sticker set against an EasyGIF platform profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sticker_package import load_profile, validate_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--profile", default="wechat-submit")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = validate_package(args.package, load_profile(args.profile))
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text, encoding="utf-8")
    print(text, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

