from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_skills import Validator


class ValidateSkillsTests(unittest.TestCase):
    def test_public_vocabulary_rejects_agent_specific_branding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Install with " + "Code" + "x.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_public_vocabulary(path)
            self.assertTrue(
                any(
                    "private implementation terminology" in error
                    for error in validator.errors
                )
            )

    def test_api_guide_rejects_validation_render_advice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Start with one frame as a pilot.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertTrue(
                any("must not prescribe a validation render" in error for error in validator.errors)
            )

    def test_api_guide_rejects_concrete_local_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Upload `example-scene.blend`.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertTrue(
                any("concrete filenames" in error for error in validator.errors)
            )

    def test_api_route_filename_segment_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text(
                "Call `GET /api/market/extensions/repo/v2/{subject}/index.json`.\n",
                encoding="utf-8",
            )
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertEqual(validator.errors, [])

    def test_addon_owned_rclone_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text(
                "Do not invoke `rclone` directly; let the Sulu add-on own transfers.\n",
                encoding="utf-8",
            )
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertEqual(validator.errors, [])

    def test_raw_rclone_command_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text(
                "Run rclone copy from the project root to object storage.\n",
                encoding="utf-8",
            )
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertTrue(
                any("raw rclone commands" in error for error in validator.errors)
            )


if __name__ == "__main__":
    unittest.main()
