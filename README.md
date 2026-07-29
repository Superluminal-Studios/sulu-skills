# sulu-skills

**Experimental.** Agent skills for the public Superluminal (Sulu) API at
`https://api.superlumin.al`, with a preferred Blender MCP and Sulu add-on path
for render submission.

Each skill contains a concise entrypoint, a detailed HTTP reference, and agent
discovery metadata. The guides describe request methods, public paths, fields,
response contracts, side effects, and approval boundaries without prescribing
a programming language, command-line tool, or local file layout. The render
guide additionally defines how Blender MCP should hand scene and transfer work
to the Sulu add-on.

## Skills

| Skill | Covers |
| --- | --- |
| `sulu-api` | Authentication, shared request rules, account security, organizations, projects, billing, referrals, and support |
| `sulu-render` | Blender MCP and add-on submission, API fallback, cost estimation, monitoring, editing, duplication, and results |
| `sulu-storage` | Add-on-managed render transfers, project storage access, output layout, and marketplace transfer sessions |
| `sulu-production` | Production configuration, elements, tasks, revisions, review media, time, notifications, and planning |
| `sulu-market` | Buying, delivery, reviews, seller onboarding, products, media, discounts, orders, and earnings |

The public API inventory in [api-surface.json](api-surface.json) assigns every
documented user route and collection to one skill. [API-SURFACE.md](API-SURFACE.md)
explains how that inventory is organized.

## Installation

Install only the skills needed for the workflows being tested. For Blender
render submission, install `sulu-api`, `sulu-render`, and `sulu-storage`
together. `sulu-production` and `sulu-market` can be installed independently.

### Ask an agent to install a skill

Give an agent with skill-installation support the GitHub location of the
individual skill. For example:

> Install the `sulu-render` skill from
> `https://github.com/Superluminal-Studios/sulu-skills/tree/main/skills/sulu-render`.

Replace `sulu-render` in both places with any skill name from the table above.
To install the Blender render set, ask the agent to install these three
locations:

- `https://github.com/Superluminal-Studios/sulu-skills/tree/main/skills/sulu-api`
- `https://github.com/Superluminal-Studios/sulu-skills/tree/main/skills/sulu-render`
- `https://github.com/Superluminal-Studios/sulu-skills/tree/main/skills/sulu-storage`

Reload the agent's skill discovery or start a new session after installation.

### Install manually

Clone this repository, choose one skill, and copy that skill directory into the
skills directory recognized by the agent host. This example defaults to
`.agents/skills`; set `AGENT_SKILLS_DIR` when the host uses another location.

```bash
git clone --depth 1 https://github.com/Superluminal-Studios/sulu-skills.git
cd sulu-skills

SULU_SKILL_NAME=sulu-render
SULU_SKILL_DEST="${AGENT_SKILLS_DIR:-$HOME/.agents/skills}"

mkdir -p "$SULU_SKILL_DEST"
if [ -e "$SULU_SKILL_DEST/$SULU_SKILL_NAME" ]; then
  echo "Skill already installed: $SULU_SKILL_NAME"
  exit 1
fi
cp -R "skills/$SULU_SKILL_NAME" "$SULU_SKILL_DEST/$SULU_SKILL_NAME"
```

Set `SULU_SKILL_NAME` to `sulu-api`, `sulu-render`, `sulu-storage`,
`sulu-production`, or `sulu-market`. The safety check intentionally stops if
that skill is already installed instead of overwriting it. Reload skill
discovery or start a new agent session after installation.

Installing these guides does not grant Sulu access or install external
integrations. Blender render testing also requires an authenticated Sulu
account, a connected Blender MCP server, the trusted Sulu Blender add-on, and a
saved Blender project.

## Render submissions

Submitting Blender jobs is the primary workflow. When Blender MCP and the Sulu
Blender add-on are available, agents should use them together: Blender MCP
inspects and configures the live scene, the add-on captures the Blender schema,
prepares dependencies, performs transfers, and registers the job, and the Sulu
API supplies scope, pricing, approval, monitoring, and reconciliation.

Before any credential, upload, or billable action, the render skill requires a
successful read-only MCP inspection, a saved Blender project, registered Sulu
add-on operations, refreshed proof of the exact requested identity, and a
matching add-on/API project.

Direct storage and render API submission remains documented for deliberate
headless or custom-client work. An agent must choose one submission path and
must not dispatch the same billable job through both the add-on and raw API.
The guide does not recommend a separate validation render or use concrete
local filenames.

## Safety

Every skill follows [GUARDRAILS.md](GUARDRAILS.md). Agents act only for the
authenticated user, stay within confirmed organization and project scope, ask
before spending money or making consequential changes, protect credentials,
and use only endpoints documented for the requested workflow.

## Validation

Run:

```text
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

The validator checks skill structure, discovery metadata, references, links,
placeholders, syntax, API-guide style, and complete ownership of the documented
public API inventory.
