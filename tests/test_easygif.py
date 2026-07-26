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

        submission_route = json.loads(run_script(
            "select_strategy.py",
            "--scope", "local", "--family", "periodic", "--continuity", "medium",
            "--source-width", "240", "--source-height", "240", "--atlas-width", "1536",
            "--frames", "6", "--platform-profile", "wechat-submit",
        ).stdout)
        self.assertEqual(submission_route["platform_profile"], "wechat-submit")
        self.assertEqual(submission_route["platform_contract"]["max_bytes"], 500000)
        self.assertEqual(submission_route["target_format"], "gif")

        preflight = json.loads(run_script(
            "preflight_plan.py",
            "--goal", "a hand-drawn chat sticker",
            "--subject", "one sleepy cat",
            "--action", "open the jaw into a slow yawn and return",
            "--family", "deformable", "--scope", "local", "--continuity", "high",
            "--source-width", "1024", "--source-height", "1024",
            "--frames", "9", "--platform-profile", "wechat-chat",
        ).stdout)
        self.assertEqual(preflight["status"], "ready_for_execution")
        self.assertEqual(preflight["subject"], "one sleepy cat")
        self.assertEqual(preflight["generation_plan"]["frames"], 9)
        self.assertEqual(preflight["representation"], "full_frame")
        self.assertEqual(preflight["reference"]["source"], "generated")
        self.assertEqual(preflight["reference"]["status"], "locked")
        self.assertIn("validation_gates", preflight)

        needs_selection = json.loads(run_script(
            "preflight_plan.py",
            "--subject", "an unfamiliar fantasy creature",
            "--source-width", "1024", "--source-height", "1024",
            "--reference-confidence", "low",
        ).stdout)
        self.assertEqual(needs_selection["status"], "needs_user_selection")
        self.assertEqual(needs_selection["reference"]["status"], "needs-user-selection")

        video_reference = json.loads(run_script(
            "preflight_plan.py",
            "--input-source", "video", "--reference-source", "video-first-frame",
            "--source-width", "640", "--source-height", "360",
        ).stdout)
        self.assertEqual(video_reference["status"], "ready_for_execution")
        self.assertEqual(video_reference["reference"]["status"], "locked")

    def test_full_frame_route_does_not_request_layer_validation(self) -> None:
        route = json.loads(run_script(
            "select_strategy.py",
            "--scope", "cluster", "--family", "transform", "--continuity", "medium",
            "--source-width", "255", "--source-height", "256", "--atlas-width", "1536",
            "--frames", "6", "--max-bytes", "1000000",
        ).stdout)
        self.assertEqual(route["strategy"], "contact_sheet")
        self.assertEqual(route["composition_contract"]["mode"], "full_frame")
        self.assertFalse(route["preserve_static_base"])
        self.assertNotIn("region_validate", route["validators"])
        self.assertNotIn("composite_validate", route["validators"])
        self.assertNotIn("local_layers", route["fallbacks"])

        layer_route = json.loads(run_script(
            "select_strategy.py",
            "--scope", "local", "--family", "appearance", "--continuity", "medium",
            "--source-width", "16", "--source-height", "9", "--atlas-width", "1536",
            "--frames", "6", "--max-bytes", "1000000", "--trusted-region",
        ).stdout)
        self.assertEqual(layer_route["composition_contract"]["mode"], "static_base_plus_patch")
        self.assertIn("composite_validate", layer_route["validators"])
        self.assertTrue(layer_route["layer_source"]["explicit"])

        semantic_only = json.loads(run_script(
            "select_strategy.py",
            "--scope", "local", "--family", "appearance", "--continuity", "medium",
            "--source-width", "16", "--source-height", "9", "--atlas-width", "1536",
            "--frames", "6", "--max-bytes", "1000000",
        ).stdout)
        self.assertEqual(semantic_only["composition_contract"]["mode"], "full_frame")
        self.assertNotIn("composite_validate", semantic_only["validators"])

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

            clean_output = root / "clean.gif"
            run_script(
                "optimize_gif.py", str(source), str(clean_output),
                "--size", "240", "--colors", "256", "--dither", "none",
            )
            with Image.open(clean_output) as clean:
                self.assertEqual(clean.n_frames, 9)
                self.assertEqual(clean.size, (240, 240))

            final_output = root / "final.gif"
            delivery = json.loads(run_script(
                "finalize_gif.py", str(source), str(final_output),
                "--size", "240", "--max-bytes", "1000000",
                "--expect-width", "240", "--expect-height", "240",
                "--expect-frames", "9",
            ).stdout)
            self.assertEqual(delivery["status"], "delivered")
            self.assertTrue(final_output.is_file())
            self.assertTrue((root / "final-delivery.json").is_file())

    def test_optimizer_preserves_non_square_source_aspect_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.gif"
            frames = [Image.new("RGB", (320, 200), (index * 30, 120, 180)) for index in range(2)]
            frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0, format="GIF")
            for frame in frames:
                frame.close()
            output = root / "optimized.gif"
            run_script("optimize_gif.py", str(source), str(output), "--size", "240")
            validation = run_script(
                "validate_output.py", str(output), "--expect-width", "240", "--expect-height", "150",
                "--expect-frames", "2", "--require-loop", "--json",
            )
            self.assertTrue(json.loads(validation.stdout)["passed"])

    def test_optimizer_preserves_transparency_without_dither(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "transparent.gif"
            frames = []
            for index in range(3):
                image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                ImageDraw.Draw(image).ellipse(
                    (20 + index, 20, 70 + index, 70), fill=(80, 150, 220, 255)
                )
                frames.append(image)
            frames[0].save(
                source,
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
                transparency=0,
                disposal=2,
                format="GIF",
            )
            for frame in frames:
                frame.close()
            output = root / "transparent-optimized.gif"
            run_script(
                "optimize_gif.py", str(source), str(output),
                "--size", "96", "--colors", "256", "--dither", "none",
            )
            validation = json.loads(run_script(
                "validate_output.py", str(output), "--json", "--require-alpha",
            ).stdout)
            self.assertTrue(validation["passed"])

    def test_composite_validator_rejects_boundary_spill(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base_path = root / "base.png"
            base = Image.new("RGB", (64, 64), (240, 240, 240))
            base.save(base_path)
            frames_path = root / "frames"
            frames_path.mkdir()
            for index, x in enumerate((24, 26)):
                frame = base.copy()
                draw = ImageDraw.Draw(frame)
                draw.rectangle((x, 24, x + 12, 36), fill=(20, 80, 160))
                frame.save(frames_path / f"frame-{index:03d}.png")
                frame.close()
            report = json.loads(run_script(
                "composite_validate.py", str(base_path), str(frames_path),
                "--region", "20", "20", "24", "24",
            ).stdout)
            self.assertTrue(report["passed"])

            with Image.open(frames_path / "frame-001.png") as source:
                spill = source.convert("RGB")
            for y in range(20, 44):
                spill.putpixel((19, y), (0, 0, 0))
            spill.save(frames_path / "frame-001.png")
            spill.close()
            failed = run_script(
                "composite_validate.py", str(base_path), str(frames_path),
                "--region", "20", "20", "24", "24",
                expect=1,
            )
            self.assertTrue(json.loads(failed.stdout)["seam_risk"])

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

    def test_repair_plan_keeps_full_frame_drift_full_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "region.json"
            report.write_text(json.dumps({"passed": False, "violations": [2]}), encoding="utf-8")
            route = root / "route.json"
            route.write_text(json.dumps({"composition_contract": {"mode": "full_frame"}}), encoding="utf-8")
            output = run_script("repair_plan.py", "--report", str(report), "--route", str(route), expect=1)
            result = json.loads(output.stdout)
            self.assertEqual(result["composition_mode"], "full_frame")
            self.assertEqual(result["recommended_next_route"], "contact_sheet")
            self.assertTrue(any("approximate colors" in action for action in result["actions"]))

            conservative = run_script("repair_plan.py", "--report", str(report), expect=1)
            conservative_result = json.loads(conservative.stdout)
            self.assertEqual(conservative_result["composition_mode"], "unspecified")
            self.assertEqual(conservative_result["recommended_next_route"], "contact_sheet")

    def test_wechat_package_and_visual_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            for index in range(8):
                image = Image.new("RGBA", (240, 240), (245, 245, 245, 255))
                draw = ImageDraw.Draw(image)
                draw.ellipse((40 + index, 60, 170 + index, 190), fill=(40, 80, 160, 255))
                image.save(source / f"frame-{index + 1:02d}.png")
                image.close()
            package = root / "package"
            banner = root / "banner.png"
            Image.new("RGB", (750, 400), (30, 100, 140)).save(banner)
            run_script(
                "package_sticker_set.py", str(source), str(package), "--profile", "wechat-submit",
                "--banner", str(banner),
            )
            validation = json.loads(run_script(
                "validate_sticker_package.py", str(package), "--profile", "wechat-submit",
            ).stdout)
            self.assertTrue(validation["passed"])
            self.assertEqual(validation["count"], 8)
            self.assertTrue((package / "assets" / "cover.png").is_file())
            self.assertEqual(len(list((package / "assets" / "icons").glob("*.png"))), 8)

            frames = root / "frames"
            frames.mkdir()
            for index in range(3):
                image = Image.new("RGB", (64, 48), (240, 240, 240))
                ImageDraw.Draw(image).rectangle((10 + index, 10, 28 + index, 30), fill=(10, 80, 140))
                image.save(frames / f"frame-{index:03d}.png")
                image.close()
            report_path = root / "visual-qa.json"
            qa = json.loads(run_script(
                "visual_qa.py", str(frames), "--report", str(report_path), "--cell-long-edge", "64",
            ).stdout)
            self.assertTrue(qa["passed"])
            self.assertTrue((root / "contact-sheet.png").is_file())
            self.assertEqual(qa["frames"], 3)

            reference = root / "reference.png"
            Image.new("RGBA", (80, 60), (20, 30, 40, 255)).save(reference)
            candidate = root / "candidate.png"
            Image.new("RGBA", (80, 60), (20, 30, 40, 255)).save(candidate)
            lock = root / "reference-lock.json"
            result = json.loads(run_script(
                "reference_lock.py", str(reference), "--output", str(lock), "--candidate", str(candidate),
            ).stdout)
            self.assertTrue(result["passed"])
            self.assertEqual(result["reference"]["size"], [80, 60])
            self.assertEqual(result["source_kind"], "user-provided")
            self.assertEqual(result["status"], "locked")


if __name__ == "__main__":
    unittest.main()
