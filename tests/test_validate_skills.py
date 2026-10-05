from __future__ import annotations

import tempfile
import json
import unittest
from pathlib import Path

from scripts.validate_skills import ROOT, Validator


class ValidateSkillsTests(unittest.TestCase):
    def section(self):
        return json.loads((ROOT / 'api-surface.json').read_text(encoding='utf-8'))['user_mcp']

    def section_errors(self, section):
        validator = Validator()
        validator.validate_user_mcp_manifest(ROOT / 'api-surface.json', section)
        return validator.errors

    def test_user_mcp_contract_is_consistent_and_documented(self):
        section = self.section()
        names = {tool['name'] for tool in section['tools']}
        self.assertGreaterEqual(len(names), 26)
        self.assertTrue({'sulu_context_get', 'render_job_submit', 'render_jobs_delete'} <= names)
        self.assertEqual(len(section['scopes']), 8)
        self.assertEqual(sorted(section['scope_profiles']), ['sulu.render', 'sulu.render.admin'])
        self.assertEqual(self.section_errors(section), [])


    def test_user_mcp_must_be_the_production_endpoint(self):
        for field, value in (('status', 'not_deployed'), ('public_enabled', False),
                             ('scope', 'all_users_and_accounts'), ('endpoint', 'https://example.invalid/mcp')):
            with self.subTest(field=field):
                section = self.section()
                section[field] = value
                self.assertTrue(self.section_errors(section))


    def test_connect_guidance_is_consistent(self):
        validator = Validator()
        validator.validate_connect_guidance()
        self.assertEqual(validator.errors, [])


    def test_public_vocabulary_rejects_private_implementation_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Jobs are stored in " + "SQ" + "Lite.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_public_vocabulary(path)
            self.assertTrue(
                any(
                    "private implementation terminology" in error
                    for error in validator.errors
                )
            )


if __name__ == "__main__":
    unittest.main()
