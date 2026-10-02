#!/usr/bin/env python3
"""Validate the repository's skill structure without third-party dependencies."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COLLECTION_RE = re.compile(r"^_?[A-Za-z0-9][A-Za-z0-9_]*$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bFIXME\b|\bTBD\b|\[TODO:|replace this skill)",
)
YAML_LINE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):(?:[ \t]+)(.+)$")
OPENAI_FIELD_RE = re.compile(
    r'^[ \t]+(display_name|short_description|default_prompt):[ \t]+"(.*)"[ \t]*$',
    re.MULTILINE,
)
BASH_FENCE_RE = re.compile(r"```(?:bash|sh|shell)\s*\n(.*?)```", re.DOTALL)
PILOT_RENDER_RE = re.compile(
    r"(?:\bpilot\b|\bone[- ]frame\b|\bsingle[- ]frame\b|start with one frame)",
    re.IGNORECASE,
)
LOCAL_IMPLEMENTATION_RE = re.compile(
    r"(?:"
    r"\b(?:sulu_request|sulu_multipart|render_job)\.py\b"
    r"|/(?:tmp|absolute)/"
    r"|\bpython3\b"
    r"|\bgo[ \t]+run\b"
    r")",
    re.IGNORECASE,
)
RAW_RCLONE_COMMAND_RE = re.compile(
    r"\brclone(?:\.exe)?[ \t]+"
    r"(?:copy|sync|move|copyto|moveto|delete|purge|mkdir|rmdir|ls|lsf|lsjson)\b",
    re.IGNORECASE,
)
CONCRETE_FILENAME_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9_-]*\."
    r"(?:blend|csv|exr|go|jpe?g|json|mov|mp4|png|py|txt|webp|zip)\b",
    re.IGNORECASE,
)
SOURCE_FILENAME_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:go|js|sql)\b",
    re.IGNORECASE,
)
PUBLIC_SURFACE_COUNTS = {
    "custom_routes": 140,
    "collections": 34,
    "builtin_user_routes": 19,
}
# The Sulu MCP catalogue itself is generated from the released gateway
# contract; this validator checks its internal consistency and evidence.
USER_MCP_ENDPOINT = "https://mcp.superlumin.al/mcp"
USER_MCP_GUIDE = "skills/sulu-render/references/user-mcp.md"
USER_MCP_DEFAULT_SCOPE = "sulu.render"
USER_MCP_PROFILES = {
    "sulu.render": [
        "sulu.context.read",
        "sulu.render.read",
        "sulu.render.logs.read",
        "sulu.render.outputs.read",
        "sulu.render.submit",
        "sulu.render.control",
    ],
    "sulu.render.admin": ["sulu.render.delete", "sulu.render.capacity"],
}
USER_MCP_SCOPES = [scope for scopes in USER_MCP_PROFILES.values() for scope in scopes]
USER_MCP_MIN_PROTOCOLS = [
    "2026-07-28",
    "2025-11-25",
    "2025-06-18",
]
USER_MCP_AUDIENCES = {"mcp_client", "public", "first_party"}
USER_MCP_REMOVED_ROUTES = {
    "PUT /transfers/{session}",
    "POST /api/oauth/v1/identity/assertion",
}
USER_MCP_SUPERSEDED_LEGACY_ROUTES = [
    {"method":"POST","path":"/api/farm/{org_id}/jobs","replacement":"render_job_submit"},
    {"method":"PATCH","path":"/api/jobs/{org_id}/{job_id}","replacement":"render_job_template_update"},
    {"method":"POST","path":"/api/jobs/{org_id}/{job_id}/duplicate","replacement":"render_job_duplicate"},
    {"method":"PUT","path":"/api/render/capacity/{org_id}","replacement":"render_capacity_set"},
    {"method":"GET","path":"/api/farm_status/{org_id}","replacement":"render_capacity_get"},
    {"method":"POST","path":"/farm/{org_id}/api/job_status","replacement":"render_job_pause / render_job_resume"},
    {"method":"POST","path":"/farm/{org_id}/api/delete_job","replacement":"render_jobs_delete"},
    {"method":"POST","path":"/farm/{org_id}/api/task_status_many","replacement":"render_tasks_retry"},
]
USER_MCP_COLLECTION_OVERRIDES = [
    {"name":"users","closed_operations":["anonymous-list"],"replacement":"POST /api/usernames/availability"},
    {"name":"projects","closed_operations":["raw-create"],"replacement":"POST /api/projects/create"},
    {"name":"jobs","closed_operations":["raw-create","raw-update","raw-delete"],"replacement":"Sulu MCP render tools"},
]
# Exclusion -> the tool that lifts it once released (None: never lifted).
USER_MCP_EXCLUSIONS = {
    "administrator": None,
    "fleet": None,
    "workstation": None,
    "production_tracker": None,
    "account_administration": None,
    "project_creation": "render_project_ensure",
    "general_storage": None,
    "billing_purchase": None,
    "arbitrary_api": None,
    "standalone_render_cancel": "render_job_cancel",
}
TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
GENERATED_TOOLS_RE = re.compile(
    r"<!-- BEGIN GENERATED: tools -->(.*?)<!-- END GENERATED: tools -->",
    re.DOTALL,
)
# Connect commands every client-facing guide must keep in sync.
CONNECT_COMMANDS = (
    "claude mcp add --transport http sulu https://mcp.superlumin.al/mcp",
    "codex mcp add sulu --url https://mcp.superlumin.al/mcp",
    "codex mcp login sulu",
)
CURSOR_DEEPLINK_RE = re.compile(
    r"cursor://anysphere\.cursor-deeplink/mcp/install\?name=sulu&config=([A-Za-z0-9+/=_-]+)"
)
# Client configuration file names are conventions, not local project files.
CLIENT_CONFIG_FILENAMES = (".mcp.json",)
# Approval rituals that the project authority replaced.
APPROVAL_RITUAL_RE = re.compile(
    r"(?:approval packet|approves that exact request|"
    r"approval immediately before|confirm the submission with the human)",
    re.IGNORECASE,
)
PRIVATE_TERM_HASHES = {
    "0b88383acb43b5c6d3f86c074662dbd42a61a8d4093f6900b467aaedfceaaf39",
    "0cd8666848bf286d951c3d230e8b6e092fde03c3a080e3454467e496e7b14e78",
    "10e08a419e850eba1ebba18fdd28eb7ec1b7e8baa9bcc3b973e2b8891ec726be",
    "1dc7be12a594ad02dcf69b900b16046c92cbc261681585efb77abe2b42ae3845",
    "33ef32bf6c23acb95f5902d7097b7a1d5128ca061167ec0716715b0b9eeaa5f6",
    "382132701c4733c3402706cfdd3c8fc7f41f80a88dce5428d145259a41c5f12f",
    "3bc801a33ea83df414e1aeb962a52412835be99db28668ec25de73fdd4733804",
    "4c984aaa0eaf505ae56d8bf7957202ddcf9aa199077a91196ef9987b83debdb8",
    "738e22f0acab814cc0c6a9dfdd1c6a193ea278e48b07f070784d608243e68d8c",
    "7e91fe78e86739ad6d2e96c55d4f8922f6a0eb2b87245273782b7d47c8e64f4c",
    "8a6cead4385ed4394247b71692fb729b0563f8e1bd4818a8c6c82940e9e099ba",
    "ba62dbd514d499c4fcc726a21c2623c16d5eb69dc1a6b8c8c60442cb75c0ab5b",
    "d58efc4ec1ab298538e0f804b5064e9c84d411029ecb611875f48f9710558ae3",
}
NON_PUBLIC_ROUTE_SEGMENT_HASHES = {
    "3bed2cb3a3acf7b6a8ef408420cc682d5520e26976d354254f528c965612054f",
    "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
    "9fd09dc33545f9cc19b81ebd0b98c4fd8c66ed1e34de89f4c9a81e6b26dc0d54",
    "b8a9a6830909b097d07e2d65b56028efc9a3265a4de7f16f80cf6a955fb65657",
}


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.skill_names: list[str] = []

    def error(self, path: Path, message: str) -> None:
        try:
            label = path.relative_to(ROOT)
        except ValueError:
            label = path
        self.errors.append(f"{label}: {message}")

    def validate_frontmatter(self, path: Path, directory_name: str) -> None:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            self.error(path, "must begin with YAML frontmatter delimiter")
            return
        try:
            end = lines.index("---", 1)
        except ValueError:
            self.error(path, "frontmatter has no closing delimiter")
            return
        values: dict[str, str] = {}
        for line in lines[1:end]:
            if not line.strip():
                continue
            match = YAML_LINE_RE.fullmatch(line)
            if not match:
                self.error(path, f"frontmatter must use one-line key/value fields: {line!r}")
                continue
            key, value = match.groups()
            if key in values:
                self.error(path, f"duplicate frontmatter key {key!r}")
            values[key] = value.strip().strip("\"'")
        if set(values) != {"name", "description"}:
            self.error(path, "frontmatter keys must be exactly name and description")
        name = values.get("name", "")
        if name != directory_name:
            self.error(path, f"name {name!r} must match directory {directory_name!r}")
        if not NAME_RE.fullmatch(name):
            self.error(path, "name must be lowercase kebab-case")
        description = values.get("description", "")
        if not 20 <= len(description) <= 1024:
            self.error(path, "description must be 20-1024 characters")
        if len(lines) >= 500:
            self.error(path, f"SKILL.md has {len(lines)} lines; keep it below 500")
        if "GUARDRAILS.md" not in text:
            self.error(path, "must link to the shared GUARDRAILS.md")
        if "reference.md" not in text:
            self.error(path, "must route detailed material to reference.md")

    def validate_openai_yaml(self, path: Path, skill_name: str) -> None:
        if not path.is_file():
            self.error(path, "missing agents/openai.yaml")
            return
        text = path.read_text(encoding="utf-8")
        if not text.startswith("interface:\n"):
            self.error(path, "must begin with the interface mapping")
        fields = dict(OPENAI_FIELD_RE.findall(text))
        expected = {"display_name", "short_description", "default_prompt"}
        if set(fields) != expected:
            self.error(path, "must contain exactly the three required interface strings")
            return
        short = fields["short_description"]
        if not 25 <= len(short) <= 64:
            self.error(path, "short_description must be 25-64 characters")
        if f"${skill_name}" not in fields["default_prompt"]:
            self.error(path, f"default_prompt must explicitly mention ${skill_name}")
        if len(fields["default_prompt"]) > 240:
            self.error(path, "default_prompt should remain concise (240 characters max)")

    def validate_reference(self, path: Path) -> None:
        if not path.is_file():
            self.error(path, "missing required full endpoint reference")
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) > 100 and "## Contents" not in lines:
            self.error(path, "references over 100 lines need a Contents section")

    def validate_links(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            target = target.split(maxsplit=1)[0]
            if (
                not target
                or target.startswith(("#", "http://", "https://", "mailto:"))
                or target.startswith("$")
            ):
                continue
            file_part = urllib.parse.unquote(target.split("#", 1)[0])
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                self.error(path, f"local Markdown link does not resolve: {target}")

    def validate_python(self, path: Path) -> None:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            self.error(path, f"Python syntax error: {error}")

    def validate_no_placeholders(self, path: Path) -> None:
        match = PLACEHOLDER_RE.search(path.read_text(encoding="utf-8"))
        if match:
            self.error(path, f"unfinished placeholder marker {match.group(0)!r}")

    def validate_public_vocabulary(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8").casefold()
        if SOURCE_FILENAME_RE.search(text):
            self.error(path, "contains a private source filename reference")
            return
        for token in re.findall(r"[a-z0-9]+(?:[_.-][a-z0-9]+)*", text):
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if digest in PRIVATE_TERM_HASHES:
                self.error(path, "contains private implementation terminology")
                return
        for route in re.findall(r"/api/[^\s`\"')\]]+", text):
            for segment in route.split("/")[2:]:
                clean_segment = segment.rstrip(".,;:*")
                digest = hashlib.sha256(clean_segment.encode("utf-8")).hexdigest()
                if digest in NON_PUBLIC_ROUTE_SEGMENT_HASHES:
                    self.error(path, "enumerates a non-public API route")
                    return

    def validate_safe_shell_examples(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        for block in BASH_FENCE_RE.findall(text):
            if re.search(r"\bSULU_API_TOKEN\s*=", block):
                self.error(
                    path,
                    "never assign SULU_API_TOKEN inline in a shell example",
                )
                return
            if "curl" not in block:
                continue
            if (
                "api.superlumin.al" in block
                or "superlumin.al/farm/" in block
                or "Authorization:" in block
                or "Auth-Token:" in block
            ):
                self.error(
                    path,
                    "Sulu API curl examples bypass the allowlisted/redacting helpers",
                )
                return

    def validate_api_guide_style(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        pilot = PILOT_RENDER_RE.search(text)
        if pilot:
            self.error(
                path,
                f"render guidance must not prescribe a validation render: {pilot.group(0)!r}",
            )
        implementation = LOCAL_IMPLEMENTATION_RE.search(text)
        if implementation:
            self.error(
                path,
                "skills must describe the API rather than local helper commands or paths: "
                f"{implementation.group(0)!r}",
            )
        raw_transfer = RAW_RCLONE_COMMAND_RE.search(text)
        if raw_transfer:
            self.error(
                path,
                "skills may assign transfer ownership to the Sulu add-on but must not "
                "prescribe raw rclone commands: "
                f"{raw_transfer.group(0)!r}",
            )
        if BASH_FENCE_RE.search(text):
            self.error(path, "skills must use API method/path examples, not shell commands")

        ritual = APPROVAL_RITUAL_RE.search(text)
        if ritual:
            self.error(
                path,
                "render guidance must act within the project authority instead of "
                f"an approval ritual: {ritual.group(0)!r}",
            )

        visible = re.sub(r"\]\([^)]*\)", "]", text)
        visible = re.sub(
            r"(?:https?://|/api/|/farm/|/sdk/|/\.well-known/)[^\s`\"')\]]+",
            " ",
            visible,
        )
        for client_file in CLIENT_CONFIG_FILENAMES:
            visible = visible.replace(client_file, " ")
        filename = CONCRETE_FILENAME_RE.search(visible)
        if filename:
            self.error(
                path,
                "skills must use semantic placeholders instead of concrete filenames: "
                f"{filename.group(0)!r}",
            )

    def validate_manifest(self, path: Path) -> None:
        if not path.exists():
            self.error(path, "missing API coverage manifest")
            return
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.error(path, f"invalid JSON: {error}")
            return
        if manifest.get("version") != 1:
            self.error(path, "version must be 1")
        if manifest.get("baseline_status") != "historical_inventory_not_live_verification":
            self.error(path, "baseline must remain an explicitly historical inventory")
        self.validate_user_mcp_manifest(path, manifest.get("user_mcp"))
        declared_counts = manifest.get("expected_counts")
        if declared_counts != PUBLIC_SURFACE_COUNTS:
            self.error(path, "expected_counts does not match the public API inventory")
        all_route_keys: dict[str, str] = {}
        for section in ("custom_routes", "collections", "builtin_user_routes"):
            entries = manifest.get(section)
            if not isinstance(entries, list) or not entries:
                self.error(path, f"{section} must be a non-empty list")
                continue
            if len(entries) != PUBLIC_SURFACE_COUNTS[section]:
                self.error(
                    path,
                    f"{section} has {len(entries)} entries; "
                    f"expected {PUBLIC_SURFACE_COUNTS[section]}",
                )
            seen: set[str] = set()
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    self.error(path, f"{section}[{index}] must be an object")
                    continue
                owner = entry.get("skill")
                if owner not in self.skill_names:
                    self.error(path, f"{section}[{index}] has unknown skill {owner!r}")
                if section in {"custom_routes", "builtin_user_routes"}:
                    key = f"{entry.get('method')} {entry.get('path')}"
                    if entry.get("method") not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                        self.error(path, f"{section}[{index}] has invalid method")
                    if not isinstance(entry.get("path"), str) or not entry["path"].startswith("/"):
                        self.error(path, f"{section}[{index}] has invalid path")
                else:
                    key = str(entry.get("name"))
                    if not COLLECTION_RE.fullmatch(key):
                        self.error(path, f"{section}[{index}] has invalid collection name")
                if key in seen:
                    self.error(path, f"duplicate {section} entry {key!r}")
                seen.add(key)
                if section in {"custom_routes", "builtin_user_routes"}:
                    previous = all_route_keys.get(key)
                    if previous:
                        self.error(path, f"{key!r} appears in both {previous} and {section}")
                    all_route_keys[key] = section
                evidence = entry.get("evidence", f"skills/{owner}")
                if not isinstance(evidence, str):
                    self.error(path, f"{section}[{index}] has an invalid evidence path")
                    continue
                evidence_path = ROOT / evidence
                if not evidence_path.exists():
                    self.error(path, f"{section}[{index}] evidence does not exist: {evidence}")
                    continue
                if evidence_path.is_dir():
                    evidence_files = sorted(evidence_path.rglob("*.md"))
                else:
                    evidence_files = [evidence_path]
                evidence_text = "\n".join(
                    item.read_text(encoding="utf-8") for item in evidence_files
                )
                needle = (
                    key
                    if section in {"custom_routes", "builtin_user_routes"}
                    else entry.get("name")
                )
                if needle not in evidence_text:
                    self.error(
                        path,
                        f"{section}[{index}] evidence does not mention {needle!r}",
                    )

    def validate_user_mcp_manifest(self, path: Path, section: Any) -> None:
        """Production Sulu MCP surface, separate from the historical public API.

        The catalogue is generated from the released gateway contract and a
        cross-repository check keeps it in sync. This local check proves the
        section is internally consistent, matches the scope model, and that
        every tool and route is documented in the public guide.
        """
        if not isinstance(section, dict):
            self.error(path, "user_mcp must be an object")
            return
        if (section.get("status") != "production" or section.get("public_enabled") is not True
                or section.get("scope") != "user_render_only"
                or section.get("endpoint") != USER_MCP_ENDPOINT):
            self.error(path, "user_mcp must be the production, user-render-only endpoint")
        protocols = section.get("protocol_versions")
        if (not isinstance(protocols, list) or len(set(map(str, protocols))) != len(protocols)
                or any(version not in protocols for version in USER_MCP_MIN_PROTOCOLS)):
            self.error(path, "user_mcp protocol revisions lost a supported revision")
        if section.get("scopes") != USER_MCP_SCOPES:
            self.error(path, "user_mcp must declare exactly the eight fine-grained scopes")
        if (section.get("scope_profiles") != USER_MCP_PROFILES
                or section.get("default_scope") != USER_MCP_DEFAULT_SCOPE):
            self.error(path, "user_mcp scope profiles differ from sulu.render / sulu.render.admin")
        profile_of = {scope: profile for profile, scopes in USER_MCP_PROFILES.items() for scope in scopes}
        guide = ROOT / USER_MCP_GUIDE
        guide_text = guide.read_text(encoding="utf-8") if guide.is_file() else ""
        names: list[Any] = []
        entries = section.get("tools")
        if not isinstance(entries, list) or not entries:
            self.error(path, "user_mcp tools must be a non-empty list")
            entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                self.error(path, "user_mcp tool must be an object")
                continue
            name, scope = entry.get("name"), entry.get("scope")
            names.append(name)
            label = f"user_mcp tool {name!r}"
            if not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name):
                self.error(path, f"{label} has an invalid name")
            if type(entry.get("mutation")) is not bool or type(entry.get("destructive")) is not bool:
                self.error(path, f"{label} must declare boolean mutation and destructive flags")
            elif entry["destructive"] and not entry["mutation"]:
                self.error(path, f"{label} is destructive but not a mutation")
            if entry.get("skill") != "sulu-render":
                self.error(path, f"{label} must be owned by sulu-render")
            if scope == "":
                if entry.get("scope_mode") != "original_operation" or entry.get("profile") != "":
                    self.error(path, f"{label} without a scope must use its original operation scope")
            elif scope not in profile_of or entry.get("profile") != profile_of[scope]:
                self.error(path, f"{label} scope and profile differ from the scope model")
            elif str(scope).endswith(".read") and entry.get("mutation") is not False:
                self.error(path, f"{label} is a mutation under a read scope")
            if not isinstance(name, str) or f"`{name}`" not in guide_text:
                self.error(path, f"{label} lacks public guide evidence")
        planned = section.get("planned_tools")
        if not isinstance(planned, list):
            self.error(path, "user_mcp planned_tools must be a list")
            planned = []
        planned_names: list[Any] = []
        for entry in planned:
            if not isinstance(entry, dict):
                self.error(path, "user_mcp planned tool must be an object")
                continue
            name = entry.get("name")
            planned_names.append(name)
            if (not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name)
                    or entry.get("release") != "next" or entry.get("profile") not in USER_MCP_PROFILES
                    or type(entry.get("mutation")) is not bool or type(entry.get("destructive")) is not bool
                    or entry.get("skill") != "sulu-render"):
                self.error(path, f"user_mcp planned tool {name!r} is malformed")
            if not isinstance(name, str) or f"`{name}`" not in guide_text:
                self.error(path, f"user_mcp planned tool {name!r} lacks public guide evidence")
        all_names = [str(name) for name in names + planned_names]
        if len(set(all_names)) != len(all_names):
            self.error(path, "user_mcp lists a tool twice")
        block = GENERATED_TOOLS_RE.search(guide_text)
        documented = set(re.findall(r"^\| `([a-z0-9_]+)` \|", block.group(1), re.MULTILINE)) if block else set()
        if documented != set(all_names):
            self.error(path, "user_mcp tools differ from the generated tool table in the guide")
        statuses = section.get("job_statuses")
        if (not isinstance(statuses, list) or not statuses
                or any(not isinstance(status, str) or f"`{status}`" not in guide_text for status in statuses)):
            self.error(path, "user_mcp job statuses must be listed and documented")
        routes = section.get("http_routes")
        if not isinstance(routes, list) or not routes:
            self.error(path, "user_mcp HTTP routes must be a non-empty list")
            routes = []
        seen_routes: set[str] = set()
        for entry in routes:
            if not isinstance(entry, dict):
                self.error(path, "user_mcp HTTP route must be an object")
                continue
            method, route_path, audience = entry.get("method"), entry.get("path"), entry.get("audience")
            needle = f"{method} {route_path}"
            if (method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}
                    or not isinstance(route_path, str) or not route_path.startswith("/")):
                self.error(path, f"user_mcp route {needle!r} is malformed")
                continue
            on_account_api = route_path.startswith("/api/")
            allowed = {"first_party", "public"} if on_account_api else {"mcp_client", "public"}
            if audience not in USER_MCP_AUDIENCES or audience not in allowed:
                self.error(path, f"user_mcp route {needle!r} has the wrong credential audience")
            if entry.get("skill") not in {"sulu-render", "sulu-api"}:
                self.error(path, f"user_mcp route {needle!r} has an unknown owner")
            if entry.get("evidence") != USER_MCP_GUIDE:
                self.error(path, "user_mcp routes must cite their maintained public contract")
            if entry.get("release", "next") != "next":
                self.error(path, f"user_mcp route {needle!r} has an unknown release marker")
            if needle in USER_MCP_REMOVED_ROUTES:
                self.error(path, f"user_mcp documents a removed route {needle!r}")
            if needle in seen_routes:
                self.error(path, f"user_mcp route {needle!r} appears twice")
            seen_routes.add(needle)
            if f"`{needle}`" not in guide_text:
                self.error(path, f"user_mcp route lacks public guide evidence: {needle!r}")
        if "POST /mcp" not in seen_routes:
            self.error(path, "user_mcp must declare POST /mcp")
        if section.get("superseded_legacy_routes") != USER_MCP_SUPERSEDED_LEGACY_ROUTES:
            self.error(path, "user_mcp superseded legacy route inventory differs")
        if section.get("collection_overrides") != USER_MCP_COLLECTION_OVERRIDES:
            self.error(path, "user_mcp collection closure inventory differs")
        released = {str(name) for name in names}
        expected_exclusions = [
            capability for capability, lifted_by in USER_MCP_EXCLUSIONS.items() if lifted_by not in released
        ]
        if section.get("excluded_capabilities") != expected_exclusions:
            self.error(path, "user_mcp capability exclusions differ")

    def validate_connect_guidance(self) -> None:
        """Every client-facing guide carries the same supported connect commands."""
        for relative in ("README.md", USER_MCP_GUIDE, "skills/sulu-render/SKILL.md"):
            path = ROOT / relative
            if not path.is_file():
                self.error(path, "missing Sulu MCP connect guidance")
                continue
            text = path.read_text(encoding="utf-8")
            if USER_MCP_ENDPOINT not in text:
                self.error(path, "must name the Sulu MCP endpoint")
            for command in CONNECT_COMMANDS:
                if command not in text:
                    self.error(path, f"must keep the supported connect command {command!r}")
            for encoded in CURSOR_DEEPLINK_RE.findall(text):
                try:
                    padded = encoded + "=" * (-len(encoded) % 4)
                    config = json.loads(base64.urlsafe_b64decode(padded.replace("+", "-").replace("/", "_")))
                except (ValueError, json.JSONDecodeError):
                    config = None
                if config != {"url": USER_MCP_ENDPOINT}:
                    self.error(path, "Cursor install link must encode the Sulu MCP endpoint")

    def validate_blender_submission_coordination(self) -> None:
        render_skill = SKILLS / "sulu-render" / "SKILL.md"
        coordination = SKILLS / "sulu-render" / "references" / "blender-mcp.md"
        readme = ROOT / "README.md"
        required = {
            render_skill: (
                "Blender MCP",
                "Sulu Blender add-on",
                "references/blender-mcp.md",
                "Never search local caches",
                "approval_required",
                "Never add a test or validation render",
            ),
            coordination: (
                "bpy.ops.superluminal.submit_job",
                "`rclone` directly",
                "Do not also call the raw submit endpoint",
                "Before the add-on submits",
                "must not silently become the submission mechanism",
            ),
            readme: (
                "## Installation",
                "## Connect Sulu MCP",
                "Superluminal-Studios/sulu-skills/tree/main/skills/sulu-render",
                "`sulu-api`, `sulu-render`, and `sulu-storage`",
                '${AGENT_SKILLS_DIR:-$HOME/.agents/skills}',
                "Submitting Blender jobs is the primary workflow",
                "successful read-only MCP inspection",
                "must not dispatch the same billable job through both",
            ),
        }
        for path, phrases in required.items():
            if not path.is_file():
                self.error(path, "missing Blender submission coordination guide")
                continue
            text = path.read_text(encoding="utf-8")
            for phrase in phrases:
                if phrase not in text:
                    self.error(
                        path,
                        f"must preserve Blender MCP and Sulu add-on guidance: {phrase!r}",
                    )

    def run(self) -> int:
        if not SKILLS.is_dir():
            self.error(SKILLS, "skills directory is missing")
            return self.finish()
        directories = sorted(path for path in SKILLS.iterdir() if path.is_dir())
        self.skill_names = [path.name for path in directories]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for directory in directories:
            skill_name = directory.name
            skill_file = directory / "SKILL.md"
            if not skill_file.is_file():
                self.error(skill_file, "missing")
                continue
            self.validate_frontmatter(skill_file, skill_name)
            self.validate_reference(directory / "reference.md")
            for reference in sorted((directory / "references").glob("*.md")):
                self.validate_reference(reference)
            self.validate_openai_yaml(directory / "agents" / "openai.yaml", skill_name)
            if f"`{skill_name}`" not in readme:
                self.error(ROOT / "README.md", f"does not route the {skill_name} skill")

        markdown_files = sorted(ROOT.rglob("*.md"))
        for path in markdown_files:
            if ".git" in path.parts:
                continue
            self.validate_links(path)
            self.validate_no_placeholders(path)
            self.validate_public_vocabulary(path)
            self.validate_safe_shell_examples(path)
            if SKILLS in path.parents:
                self.validate_api_guide_style(path)
        for path in sorted(ROOT.rglob("*.py")):
            if ".git" not in path.parts:
                self.validate_python(path)
                self.validate_public_vocabulary(path)
        for suffix in ("*.json", "*.yaml", "*.yml"):
            for path in sorted(ROOT.rglob(suffix)):
                if ".git" not in path.parts:
                    self.validate_public_vocabulary(path)

        self.validate_manifest(ROOT / "api-surface.json")
        self.validate_connect_guidance()
        self.validate_blender_submission_coordination()
        return self.finish()

    def finish(self) -> int:
        if self.errors:
            for error in sorted(self.errors):
                print(f"ERROR {error}", file=sys.stderr)
            print(f"Validation failed with {len(self.errors)} error(s).", file=sys.stderr)
            return 1
        print(
            f"Validated {len(self.skill_names)} skills, metadata, references, links, "
            "Python syntax, and API coverage."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(Validator().run())
