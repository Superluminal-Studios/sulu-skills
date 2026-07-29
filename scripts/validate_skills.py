#!/usr/bin/env python3
"""Validate the repository's skill structure without third-party dependencies."""

from __future__ import annotations

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
    r"|\brclone\b"
    r")",
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
        for token in re.findall(r"[a-z0-9_.-]+", text):
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
        if BASH_FENCE_RE.search(text):
            self.error(path, "skills must use API method/path examples, not shell commands")

        visible = re.sub(r"\]\([^)]*\)", "]", text)
        visible = re.sub(
            r"(?:https?://|/api/|/farm/)[^\s`\"')\]]+",
            " ",
            visible,
        )
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
