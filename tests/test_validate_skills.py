from __future__ import annotations

import tempfile
import json
import copy
import unittest
from pathlib import Path

from scripts.validate_skills import ROOT, Validator


class ValidateSkillsTests(unittest.TestCase):
    def candidate(self):
        return json.loads((ROOT / 'api-surface.json').read_text(encoding='utf-8'))['candidate_user_mcp']

    def candidate_errors(self, candidate):
        validator = Validator()
        validator.validate_candidate_manifest(ROOT / 'api-surface.json', candidate)
        return validator.errors

    def test_candidate_exact_closed_contract_and_public_evidence(self):
        candidate = self.candidate()
        self.assertEqual(len(candidate['tools']), 23)
        self.assertEqual(len(candidate['scopes']), 8)
        self.assertEqual(self.candidate_errors(candidate), [])

    def test_candidate_rejects_missing_duplicate_or_extra_tool(self):
        for mutation in ('missing', 'duplicate', 'extra'):
            with self.subTest(mutation=mutation):
                candidate = self.candidate()
                if mutation == 'missing':
                    candidate['tools'].pop()
                elif mutation == 'duplicate':
                    candidate['tools'].append(copy.deepcopy(candidate['tools'][0]))
                else:
                    candidate['tools'].append({'name': 'arbitrary_api_call', 'scope': '', 'mutation': True,
                                               'destructive': False, 'skill': 'sulu-render'})
                self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_rejects_scope_and_write_annotation_drift(self):
        for field, value in (('scope', 'sulu.render.capacity'), ('mutation', True), ('destructive', 0)):
            with self.subTest(field=field):
                candidate = self.candidate()
                candidate['tools'][0][field] = value
                self.assertTrue(self.candidate_errors(candidate))
        candidate = self.candidate()
        candidate['scopes'].append('sulu.everything')
        self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_operation_polling_is_bound_to_original_scope(self):
        candidate = self.candidate()
        operation = next(tool for tool in candidate['tools'] if tool['name'] == 'render_operation_get')
        self.assertEqual(operation['scope'], '')
        operation.pop('scope_mode')
        self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_cannot_claim_public_deployment(self):
        for field, value in (('status', 'deployed'), ('public_enabled', True), ('scope', 'all_users_and_accounts')):
            candidate = self.candidate()
            candidate[field] = value
            self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_rejects_route_expansion_or_wrong_credential_audience(self):
        for field, value in (('path', '/api/render/v1/arbitrary'), ('audience', 'first_party'),
                             ('evidence', 'skills/sulu-api/reference.md')):
            candidate = self.candidate()
            candidate['http_routes'][0][field] = value
            self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_closures_and_exclusions_cannot_disappear(self):
        for field in ('closed_legacy_routes', 'collection_overrides', 'excluded_capabilities', 'protocol_versions'):
            candidate = self.candidate()
            candidate[field].pop()
            self.assertTrue(self.candidate_errors(candidate))

    def test_candidate_malformed_sections_fail_safely(self):
        for field, value in (('tools', None), ('tools', [None]), ('http_routes', None), ('http_routes', [None])):
            candidate = self.candidate()
            candidate[field] = value
            self.assertTrue(self.candidate_errors(candidate))

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
