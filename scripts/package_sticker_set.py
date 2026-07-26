"""Package ordered stickers and derived WeChat delivery assets."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from sticker_package import load_profile, natural_key, render_png, validate_package


SUPPORTED_INPUTS = {".gif", ".png", ".webp", ".jpg", ".jpeg"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="directory containing ordered sticker files")
    parser.add_argument("output", type=Path)
    parser.add_argument("--profile", default="wechat-submit")
    parser.add_argument("--banner", type=Path)
    parser.add_argument("--cover", type=Path)
    parser.add_argument("--chat-icon", type=Path)
    parser.add_argument("--clean", action="store_true", help="remove only the selected output directory before packaging")
    args = parser.parse_args()
    profile = load_profile(args.profile)
    if not args.input.is_dir():
        raise SystemExit(f"input directory not found: {args.input}")
    sources = sorted(
        [path for path in args.input.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_INPUTS],
        key=natural_key,
    )
    if not sources:
        raise SystemExit("input directory contains no supported sticker files")
    if args.clean and args.output.exists():
        # The caller named this exact output directory; never broaden cleanup.
        shutil.rmtree(args.output)
    stickers = args.output / "stickers"
    stickers.mkdir(parents=True, exist_ok=True)
    for index, source in enumerate(sources, 1):
        destination = stickers / f"{index:02d}{source.suffix.lower()}"
        shutil.copy2(source, destination)

    assets = args.output / "assets"
    first = stickers / f"01{sources[0].suffix.lower()}"
    derived = profile.get("derived_assets", {})
    if args.cover:
        shutil.copy2(args.cover, assets / "cover.png")
    elif "cover" in derived:
        render_png(first, assets / "cover.png", (derived["cover"]["width"], derived["cover"]["height"]))
    if args.chat_icon:
        shutil.copy2(args.chat_icon, assets / "chat_icon.png")
    elif "chat_icon" in derived:
        render_png(first, assets / "chat_icon.png", (derived["chat_icon"]["width"], derived["chat_icon"]["height"]))
    if "item_icon" in derived:
        size = (derived["item_icon"]["width"], derived["item_icon"]["height"])
        for path in sorted(stickers.iterdir(), key=natural_key):
            render_png(path, assets / "icons" / f"{path.stem}.png", size)
    if args.banner:
        shutil.copy2(args.banner, assets / "banner.png")

    report = validate_package(args.output, profile)
    (args.output / "package-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema": "easygif/sticker-package-v1",
        "profile": profile["id"],
        "source": str(args.input),
        "output": str(args.output),
        "stickers": [str(path.relative_to(args.output)) for path in sorted(stickers.iterdir(), key=natural_key)],
        "assets": [str(path.relative_to(args.output)) for path in sorted((args.output / "assets").rglob("*"), key=natural_key) if path.is_file()],
        "validation": "package-validation.json",
        "notes": profile.get("notes", []),
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

