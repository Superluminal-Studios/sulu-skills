from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_skills import Validator


class ValidateSkillsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
