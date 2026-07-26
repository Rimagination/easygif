from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_script(name: str, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        text=True,
        capture_output=True,
    )
    if result.returncode != expect:
        raise AssertionError(f"{name} returned {result.returncode}: {result.stdout}\n{result.stderr}")
    return result


class AdaptiveMediaForgeTests(unittest.TestCase):
    def test_route_and_motion_recipe_are_object_agnostic(self) -> None:
        route = json.loads(run_script(
            "select_strategy.py",
            "--scope", "local", "--family", "appearance", "--continuity", "medium",
            "--source-width", "16", "--source-height", "9", "--atlas-width", "1536",
            "--frames", "6", "--max-bytes", "1000000",
        ).stdout)
        self.assertEqual(route["target_format"], "gif")
        self.assertIn("backend_candidates", route)
        self.assertIn("repair_policy", route)
        recipe = json.loads(run_script(
            "motion_recipe.py", "--family", "mixed", "--scope", "cluster", "--continuity", "high",
            "--subject", "a paper lantern", "--region", "lantern body",
        ).stdout)
        self.assertEqual(recipe["subject"], "a paper lantern")
        self.assertLessEqual(len(recipe["micro_motions"]), 2)
        self.assertGreaterEqual(len(recipe["micro_motions"]), 1)
        self.assertIn("camera and framing", recipe["locked_invariants"])

    def test_grid_gate_rejects_wrong_cell_aspect_and_slices_valid_atlas(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad = root / "bad.png"
            Image.new("RGB", (600, 600), "white").save(bad)
            run_script(
                "validate_grid_geometry.py",
                str(bad),
                "--rows", "2",
                "--cols", "2",
                "--source-width", "4",
                "--source-height", "3",
                expect=1,
            )

            atlas = root / "atlas.png"
            canvas = Image.new("RGB", (1200, 600), "white")
            draw = ImageDraw.Draw(canvas)
            for index in range(6):
                x = (index % 3) * 400
                y = (index // 3) * 300
                draw.rectangle((x + 4, y + 4, x + 390, y + 280), fill=(index * 30, 100, 180))
            canvas.save(atlas)
            out = root / "frames"
            run_script(
                "slice_grid.py",
                str(atlas), str(out),
                "--rows", "2", "--cols", "3", "--frames", "5",
                "--source-width", "4", "--source-height", "3",
            )
            self.assertEqual(len(list(out.glob("frame-*.png"))), 5)

    def test_budget_optimizer_and_output_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gif"
            frames = []
            for index in range(9):
                image = Image.new("RGBA", (240, 240), (245, 190, 120, 255))
                draw = ImageDraw.Draw(image)
                draw.ellipse((30 + index * 3, 70, 150 + index * 3, 190), fill=(40, 80, 150, 255))
                frames.append(image)
            frames[0].save(source, save_all=True, append_images=frames[1:], duration=125, loop=0, format="GIF")
            for frame in frames:
                frame.close()
            output = root / "optimized.gif"
            run_script(
                "optimize_gif.py", str(source), str(output),
                "--size", "240", "--max-bytes", "50000", "--min-size", "64",
            )
            validation = run_script(
                "validate_output.py", str(output), "--max-bytes", "50000",
                "--expect-width", "240", "--expect-height", "240",
                "--expect-frames", "9", "--require-loop", "--json",
            )
            report = json.loads(validation.stdout)
            self.assertTrue(report["passed"])

    def test_repair_plan_prioritizes_temporal_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "temporal.json"
            report.write_text(json.dumps({
                "passed": False,
                "spike_boundaries": [3],
                "loop_spike": True,
            }), encoding="utf-8")
            output = run_script("repair_plan.py", "--report", str(report), expect=1)
            result = json.loads(output.stdout)
            self.assertEqual(result["status"], "repair_required")
            self.assertEqual(result["recommended_next_route"], "keyframes_then_interpolation")
            self.assertTrue(any("timeline" in action for action in result["actions"]))


if __name__ == "__main__":
    unittest.main()
