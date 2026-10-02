from __future__ import annotations

import base64
import tempfile
import json
import copy
import unittest
from pathlib import Path
from unittest import mock

from scripts.validate_skills import CONNECT_COMMANDS, ROOT, USER_MCP_ENDPOINT, USER_MCP_GUIDE, Validator


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

    def test_user_mcp_rejects_missing_duplicate_or_extra_tool(self):
        for mutation in ('missing', 'duplicate', 'extra'):
            with self.subTest(mutation=mutation):
                section = self.section()
                if mutation == 'missing':
                    section['tools'].pop()
                elif mutation == 'duplicate':
                    section['tools'].append(copy.deepcopy(section['tools'][0]))
                else:
                    section['tools'].append({'name': 'arbitrary_api_call', 'scope': 'sulu.render.submit',
                                               'profile': 'sulu.render', 'mutation': True,
                                               'destructive': False, 'skill': 'sulu-render'})
                self.assertTrue(self.section_errors(section))

    def test_user_mcp_rejects_scope_and_write_annotation_drift(self):
        for field, value in (('scope', 'sulu.render.capacity'), ('mutation', True), ('destructive', 0),
                             ('profile', 'sulu.render.admin')):
            with self.subTest(field=field):
                section = self.section()
                section['tools'][0][field] = value
                self.assertTrue(self.section_errors(section))
        section = self.section()
        section['scopes'].append('sulu.everything')
        self.assertTrue(self.section_errors(section))
        section = self.section()
        section['scope_profiles']['sulu.render'].append('sulu.render.delete')
        self.assertTrue(self.section_errors(section))

    def test_user_mcp_admin_tools_need_the_admin_profile(self):
        section = self.section()
        delete = next(tool for tool in section['tools'] if tool['name'] == 'render_jobs_delete')
        self.assertEqual((delete['profile'], delete['destructive']), ('sulu.render.admin', True))
        delete['profile'] = 'sulu.render'
        self.assertTrue(self.section_errors(section))

    def test_user_mcp_operation_polling_is_bound_to_original_scope(self):
        section = self.section()
        operation = next(tool for tool in section['tools'] if tool['name'] == 'render_operation_get')
        self.assertEqual(operation['scope'], '')
        operation.pop('scope_mode')
        self.assertTrue(self.section_errors(section))

    def test_user_mcp_must_be_the_production_endpoint(self):
        for field, value in (('status', 'not_deployed'), ('public_enabled', False),
                             ('scope', 'all_users_and_accounts'), ('endpoint', 'https://example.invalid/mcp')):
            with self.subTest(field=field):
                section = self.section()
                section[field] = value
                self.assertTrue(self.section_errors(section))

    def test_user_mcp_rejects_route_expansion_wrong_audience_or_removed_routes(self):
        for field, value in (('path', '/api/render/v1/arbitrary'), ('audience', 'first_party'),
                             ('evidence', 'skills/sulu-api/reference.md')):
            with self.subTest(field=field):
                section = self.section()
                section['http_routes'][0][field] = value
                self.assertTrue(self.section_errors(section))
        for method, path in (('PUT', '/transfers/{session}'), ('POST', '/api/oauth/v1/identity/assertion')):
            with self.subTest(route=path):
                section = self.section()
                section['http_routes'].append({'method': method, 'path': path, 'audience': 'mcp_client'
                                                 if not path.startswith('/api/') else 'first_party',
                                                 'skill': 'sulu-render',
                                                 'evidence': 'skills/sulu-render/references/user-mcp.md'})
                self.assertTrue(self.section_errors(section))

    def test_user_mcp_closures_and_exclusions_cannot_disappear(self):
        for field in ('superseded_legacy_routes', 'collection_overrides', 'excluded_capabilities',
                      'protocol_versions'):
            with self.subTest(field=field):
                section = self.section()
                section[field].pop()
                self.assertTrue(self.section_errors(section))

    def test_user_mcp_malformed_sections_fail_safely(self):
        for field, value in (('tools', None), ('tools', [None]), ('http_routes', None), ('http_routes', [None]),
                             ('planned_tools', None), ('planned_tools', [None])):
            with self.subTest(field=field, value=value):
                section = self.section()
                section[field] = value
                self.assertTrue(self.section_errors(section))

    def test_connect_guidance_is_consistent(self):
        validator = Validator()
        validator.validate_connect_guidance()
        self.assertEqual(validator.errors, [])

    def test_connect_guidance_rejects_a_wrong_cursor_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'skills/sulu-render/references').mkdir(parents=True)
            commands = '\n'.join(CONNECT_COMMANDS)
            wrong = base64.b64encode(b'{"url":"https://example.invalid/mcp"}').decode()
            text = (f'{USER_MCP_ENDPOINT}\n{commands}\n'
                    f'cursor://anysphere.cursor-deeplink/mcp/install?name=sulu&config={wrong}\n')
            for relative in ('README.md', USER_MCP_GUIDE, 'skills/sulu-render/SKILL.md'):
                (root / relative).write_text(text, encoding='utf-8')
            with mock.patch('scripts.validate_skills.ROOT', root):
                validator = Validator()
                validator.validate_connect_guidance()
            self.assertTrue(any('Cursor install link' in error for error in validator.errors))

    def test_render_guide_rejects_approval_rituals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Report the full approval packet before submitting.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_api_guide_style(path)
            self.assertTrue(any("project authority" in error for error in validator.errors))

    def test_client_config_filename_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Add the server to `.mcp.json` and read `GET /sdk/manifest.json`.\n",
                            encoding="utf-8")
            validator = Validator()
            validator.validate_api_guide_style(path)
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

    def test_public_vocabulary_allows_documented_client_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guide.md"
            path.write_text("Connect from Claude Code, Codex or Cursor.\n", encoding="utf-8")
            validator = Validator()
            validator.validate_public_vocabulary(path)
            self.assertEqual(validator.errors, [])

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
