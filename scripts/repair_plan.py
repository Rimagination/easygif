"""Turn validation reports into safe, actionable repair decisions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_reports(paths: list[Path]) -> list[tuple[str, dict[str, object]]]:
    reports = []
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"invalid validation report {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise SystemExit(f"validation report must be an object: {path}")
        reports.append((path.stem, value))
    return reports


def load_route(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid route plan {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"route plan must be an object: {path}")
    return value


def plan_repairs(
    reports: list[tuple[str, dict[str, object]]],
    route: dict[str, object] | None = None,
) -> dict[str, object]:
    issues = []
    actions = []
    next_route = None
    composition = route.get("composition_contract", {}) if route else {}
    # A missing route is intentionally conservative: a report alone does not
    # prove that a trustworthy alpha/mask exists, so never recommend an
    # improvised layer repair by default.
    full_frame_route = composition.get("mode") != "static_base_plus_patch"
    for name, report in reports:
        if report.get("passed", True):
            continue
        reason = str(report.get("reason", "validation failed"))
        issue = {"stage": name, "reason": reason}
        if "spike_boundaries" in report or "loop_spike" in report:
            issue["kind"] = "temporal"
            actions.append("rebuild the phase timeline and replace the offending keyframe boundary")
            actions.append("use a shorter, lower-amplitude motion or localize interpolation to the approved region")
            next_route = next_route or "keyframes_then_interpolation"
        elif "violations" in report or "outside_ratio" in str(report):
            issue["kind"] = "region"
            if full_frame_route:
                issue["interpretation"] = "full-frame scene drift, not permission to cut out a subject"
                actions.append("treat the region report as a diagnostic of full-frame drift")
                actions.append("do not derive a foreground mask from approximate colors or paste a generated subject onto a static background")
                actions.append("regenerate full-frame keyframes/contact-sheet frames with locked camera, background, and text")
                actions.append("run temporal and output validation again; use a layer route only when an explicit alpha/mask exists")
                next_route = next_route or "contact_sheet"
            else:
                actions.append("tighten the region or mask and regenerate only the local patch")
                actions.append("keep the static base layer and re-run region and composite validation before encoding")
                actions.append("reject the composite if the mask boundary changes outside the approved region")
                next_route = next_route or "parametric_or_local_layers"
        elif "aspect" in reason or "divisible" in report or "cell_relative_error" in report:
            issue["kind"] = "geometry"
            actions.append("re-plan the grid using the actual source and atlas aspect")
            actions.append("regenerate the atlas; never crop or stretch a bad cell as a repair")
            next_route = next_route or "contact_sheet"
        elif "bytes" in reason or "estimated" in reason or report.get("budget_met_by_estimate") is False:
            issue["kind"] = "budget"
            actions.append("retry encoding with fewer colors, then smaller dimensions, then fewer playback frames")
            actions.append("preserve the source aspect with contain fit and verify the actual encoded bytes")
        else:
            issue["kind"] = "output"
            actions.append("inspect the first, middle, last, and loop-boundary frames")
            actions.append("fall back to a more deterministic representation before regenerating")
            next_route = next_route or "contact_sheet"
        issues.append(issue)

    deduped_actions = list(dict.fromkeys(actions))
    if not issues:
        summary = "all supplied validation reports passed"
        status = "passed"
    else:
        summary = f"{len(issues)} validation stage(s) failed; repair before final packaging"
        status = "repair_required"
    return {
        "schema": "easygif/repair-plan-v1",
        "status": status,
        "summary": summary,
        "issues": issues,
        "actions": deduped_actions,
        "recommended_next_route": next_route,
        "composition_mode": composition.get("mode", "unspecified"),
        "do_not": [
            "do not hide a geometry failure by cropping",
            "do not use stronger interpolation to conceal inconsistent keyframes",
            "do not optimize bytes before spatial and temporal validation passes",
            "do not convert a full-frame drift failure into an unvalidated foreground/background split",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, action="append", required=True)
    parser.add_argument("--route", type=Path, help="optional route.json used to distinguish full-frame drift from layer failure")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = plan_repairs(load_reports(args.report), load_route(args.route))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
