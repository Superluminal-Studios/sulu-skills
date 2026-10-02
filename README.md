# sulu-skills

> **Secret source:** In the Sulu superrepo checkout, resolve real credentials
> through `../.secrets/SECRETS_INDEX.md` and verify them with the superrepo
> secret audit. These guides document variables and API contracts only; never
> copy values from docs or `.secrets/discovered/` evidence.

Agent skills for Superluminal (Sulu). Render work goes through the Sulu MCP
server at `https://mcp.superlumin.al/mcp` (production). The public account API
at `https://api.superlumin.al` covers accounts, billing, storage, production
tracking and the market, and its skills remain experimental.

Each skill contains a concise entrypoint, a detailed reference, and agent
discovery metadata. The guides describe tools, request methods, public paths,
fields, response contracts, side effects, and when to ask the human. The
render guide also defines how Blender MCP, the `sulu-render` SDK and the Sulu
add-on share scene and transfer work.

## Connect Sulu MCP

Sulu MCP uses OAuth sign-in in the browser; there is no API key. At consent
the human picks an organization and projects and sets a budget. The agent then
renders inside that authority without asking again.

| Client | Connect |
| --- | --- |
| Claude Code | `claude mcp add --transport http sulu https://mcp.superlumin.al/mcp`, then run `/mcp` and sign in |
| Codex | `codex mcp add sulu --url https://mcp.superlumin.al/mcp`, then `codex mcp login sulu` |
| Cursor | Open `cursor://anysphere.cursor-deeplink/mcp/install?name=sulu&config=eyJ1cmwiOiJodHRwczovL21jcC5zdXBlcmx1bWluLmFsL21jcCJ9` |
| Claude.ai and Claude Desktop | Settings, Connectors, Add custom connector, URL `https://mcp.superlumin.al/mcp` |
| Any MCP client with a project config | Add the server to `.mcp.json` as shown below |

```json
{"mcpServers":{"sulu":{"type":"http","url":"https://mcp.superlumin.al/mcp"}}}
```

For local packaging and bulk downloads, use the `sulu-render` SDK from
`https://mcp.superlumin.al/.well-known/sulu-sdk`:

```bash
sulu-render login
sulu-render context
sulu-render jobs
sulu-render submit --frames 1-50 <scene>
sulu-render download --job <job> --output <directory>
```

`context`, `jobs` and `submit --frames` need SDK 0.3 or later. Run
`sulu-render <command> --help` for every option. The
[Sulu MCP guide](skills/sulu-render/references/user-mcp.md) lists every tool,
scope, lifetime and route.

## Skills

| Skill | Covers |
| --- | --- |
| `sulu-api` | Authentication, shared request rules, account security, organizations, projects, billing, referrals, and support |
| `sulu-render` | Sulu MCP rendering within a project budget, Blender MCP and add-on coordination, monitoring, control, and output download |
| `sulu-storage` | Add-on-managed render transfers, project storage access, output layout, and marketplace transfer sessions |
| `sulu-production` | Production configuration, elements, tasks, revisions, review media, time, notifications, and planning |
| `sulu-market` | Buying, delivery, reviews, seller onboarding, products, media, discounts, orders, and earnings |

The public API inventory in [api-surface.json](api-surface.json) assigns every
documented user route and collection to one skill. [API-SURFACE.md](API-SURFACE.md)
explains how that inventory is organized.

## Installation

Install only the skills needed for the workflows being tested. With Sulu MCP,
`sulu-render` alone covers render work. For the add-on path and legacy
integrations, install `sulu-api`, `sulu-render`, and `sulu-storage` together.
`sulu-production` and `sulu-market` can be installed independently.

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
integrations. Rendering also requires a Sulu account connected through
[Connect Sulu MCP](#connect-sulu-mcp) and a saved Blender project.

## Render submissions

Submitting Blender jobs is the primary workflow. With Sulu MCP connected, the
agent resolves the deliverable from the request and the scene, packages and
uploads with the `sulu-render` SDK, submits, follows the job, and downloads
the outputs. It does not ask again inside the project authority, never adds a
test or validation render, and finishes when the requested outputs exist
locally.

Blender MCP inspects and saves the live scene. The Sulu Blender add-on remains
available when the human asks for it; that path runs outside the project
budget, so the agent asks once before submitting. Before that it needs a
successful read-only MCP inspection of the saved scene. An agent must choose
one submission path and must not dispatch the same billable job through both
the add-on and Sulu MCP. The legacy account API's render writes are
documented for older integrations only.

## Safety

Every skill follows [GUARDRAILS.md](GUARDRAILS.md). Agents act only for the
authenticated user and stay within the organization, projects and budget the
human approved. They ask before buying credits, before spending without a
project authority, and before consequential changes outside it. They protect
credentials and use only tools and endpoints documented for the workflow.

## Validation

Run:

```text
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

The validator checks skill structure, discovery metadata, references, links,
placeholders, syntax, API-guide style, connect commands, and complete
ownership of the documented public API inventory. The Sulu MCP tool table,
statuses and error codes are generated from the released server contract; do
not edit the marked blocks by hand.
