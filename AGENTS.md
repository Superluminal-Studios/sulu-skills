# sulu-skills Agent Guide

## Scope

This repository contains guides for the public Sulu API, recommended
Blender MCP and Sulu add-on coordination for render submission,
machine-readable API ownership data, and documentation validation.

## Rules

- Document only endpoints intended for authenticated users or public catalog
  access. Do not enumerate privileged or service-only routes.
- Keep each skill focused on HTTP methods, public paths, request fields,
  response contracts, side effects, and behavioral guardrails.
- Do not prescribe local commands, helper programs, concrete filenames, or a
  particular client implementation.
- For Blender submission, prefer registered Sulu add-on operations through
  Blender MCP. Assign schema, dependency, and transfer work to the add-on
  without documenting private modules or raw transfer commands.
- Do not include infrastructure vendors, data-store technology, private source
  layout, deployment details, internal role names, or implementation-specific
  authorization behavior.
- Never include real tokens, signed URLs, storage credentials, customer data,
  or secret values. Use semantic placeholders.
- Never recommend a separate validation render. Estimate the requested render
  conservatively from current pricing and an honest runtime assumption or
  relevant completed-job evidence.
- Keep [GUARDRAILS.md](GUARDRAILS.md) as the shared conduct policy. Do not
  weaken it in an individual skill.

## Layout

- `skills/<name>/SKILL.md`: concise entrypoint.
- `skills/<name>/reference.md`: detailed public endpoint reference.
- `skills/<name>/agents/openai.yaml`: discovery metadata.
- `skills/<name>/references/`: optional domain-specific references.
- `api-surface.json`: public route and collection ownership.
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
