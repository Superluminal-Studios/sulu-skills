# sulu-skills Agent Guide

## Scope

This repository contains guides for the public Sulu API and the Sulu MCP
render server, Blender MCP and Sulu add-on coordination for render submission,
machine-readable API ownership data, and documentation validation.

## Rules

- Document only endpoints intended for authenticated users or public catalog
  access. Do not enumerate privileged or service-only routes.
- Keep each skill focused on HTTP methods, public paths, request fields,
  response contracts, side effects, and behavioral guardrails.
- Document the one supported Sulu MCP connect command per client (endpoint
  `https://mcp.superlumin.al/mcp`) and the public `sulu-render` SDK commands.
  Keep them identical in the README, the render skill and the Sulu MCP guide.
  Otherwise do not prescribe local commands, helper programs, concrete
  filenames, or a particular client implementation, and never document
  private modules of the SDK, the add-on or any client.
- For Blender submission, prefer Sulu MCP with the `sulu-render` SDK, which
  runs inside the project authority. On the add-on path, use registered Sulu
  add-on operations through Blender MCP and assign schema, dependency, and
  transfer work to the add-on without documenting private modules or raw
  transfer commands.
- Do not include infrastructure vendors, data-store technology, private source
  layout, deployment details, internal role names, or implementation-specific
  authorization behavior.
- Never include real tokens, signed URLs, storage credentials, customer data,
  or secret values. Use semantic placeholders.
- Never recommend a separate validation render. Resolve the deliverable from
  the request and the scene, and treat the requested outputs existing locally
  as completion.
- Agents act within the Sulu MCP project authority the human set at consent.
  Ask only when no authority exists or a tool returns `approval_required`,
  for deletion or capacity changes without admin access, and before buying
  credits. Do not add approval packets or per-call confirmations to a skill.
- Keep [GUARDRAILS.md](GUARDRAILS.md) as the shared conduct policy. Do not
  weaken it in an individual skill.

## Layout

- `skills/<name>/SKILL.md`: concise entrypoint.
- `skills/<name>/reference.md`: detailed public endpoint reference.
- `skills/<name>/agents/openai.yaml`: discovery metadata.
- `skills/<name>/references/`: optional domain-specific references.
- `api-surface.json`: public route and collection ownership. Its `user_mcp`
  section, and the marked tool, status and error blocks in
  `skills/sulu-render/references/user-mcp.md`, are generated from the
  released gateway contract by the Sulu superrepo. Do not edit them by hand.
- `API-SURFACE.md`: public inventory overview.
- `GUARDRAILS.md`: shared conduct rules.

## Verification

Run:

```text
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

Run the skill-creator quick validator against every changed skill. A documented
endpoint without an owning skill, an unresolved reference, or private
implementation terminology is a release-blocking defect.

From a Sulu superrepo checkout, `bin/sync-mcp-surface` regenerates the
`user_mcp` inventory and the marked Sulu MCP blocks from the released server
contract, and `bin/sync-mcp-surface --check` fails when they are stale.
