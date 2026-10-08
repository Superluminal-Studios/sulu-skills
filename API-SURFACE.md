# Sulu public API inventory

This is the human-readable companion to [api-surface.json](api-surface.json).
The inventory covers only public and authenticated-user workflows. The original
route counts are a historical July 29 inventory, not a live production audit.
The separate `user_mcp` section describes the production Sulu MCP render
surface and does not change those historical counts.

## Coverage

The inventory maps:

- 140 Sulu-specific public or authenticated route pairs;
- 34 user-accessible collections; and
- 19 shared authentication, record, file, and realtime route pairs.

Every entry names one owning skill. The validator confirms that the owning
skill documents the route or collection and that no two inventory sections
claim the same route.

## Ownership

| Skill | Public API domain |
| --- | --- |
| `sulu-api` | Authentication, records, account lifecycle, organizations, projects, billing, referrals, and support |
| `sulu-production` | Production configuration, work tracking, review, media, and planning |
| `sulu-render` | Render settings, estimates, submission, job controls, and results |
| `sulu-storage` | Project storage and marketplace transfer sessions |
| `sulu-market` | Catalog, checkout, delivery, reviews, seller onboarding, product management, orders, and earnings |

Cross-domain workflows have one primary owner and link to the other relevant
skills. For example, storage owns byte transfer while render owns the
spend-producing submission.

## Inclusion policy

Include an operation only when it is part of a documented user workflow.
Do not inventory or describe privileged administration, operational controls,
service-to-service traffic, inbound integrations, diagnostics, or deployment
surfaces. Their absence is intentional and does not imply permission to
discover or call them.

An HTTP success response is not sufficient authorization. Agents must still
confirm the signed-in identity, organization, project, role, target, approval,
and conduct requirements described by the owning skill.

## Maintenance

When the public API changes:

1. update the owning skill and its detailed reference;
2. update the public inventory;
3. run repository validation and every changed skill's quick validator; and
4. review examples for credentials, private terminology, concrete filenames,
   and unsupported behavior.

The inventory is documentation evidence, not a substitute for runtime
authorization checks or human confirmation.

## Sulu MCP

Sulu MCP (`https://mcp.superlumin.al/mcp`) is the production render surface
for agents. Its contract is maintained in the
[Sulu MCP guide](skills/sulu-render/references/user-mcp.md). It does not
inherit this account API's wider billing, project, storage or production
capabilities. Anonymous user listing and raw project creation are closed;
username availability and idempotent project creation use the purpose-built
operations in the account guides. Agents use the Sulu MCP tool that replaces
each legacy render write and never fall back to the legacy write.

The `user_mcp` section of the inventory is generated from the released server
contract. It lists every tool with its fine-grained scope, the profile that
grants it (`sulu.render` or `sulu.render.admin`), its mutation and destructive
flags and its owning skill; tools added in the next release; job statuses;
the supported protocol revisions; public, MCP-client and first-party routes;
superseded legacy render writes; collection closures; and capability
exclusions. Operation polling uses its original operation scope rather than a
new catch-all scope.

Validation rejects a tool missing from the generated guide table, scope or
profile drift, a mutation under a read scope, duplicate entries, a removed
route coming back, a route with the wrong credential audience, missing public
evidence and a non-production status. The release process regenerates this
section from the server source and fails when it is stale; this repository
does not enumerate private service endpoints.

## SDK commands

The `sdk_cli` section lists the public commands and flags of the `sulu-render`
SDK. It is maintained by hand from the SDK's command-line help. Validation
rejects a guide that shows a `sulu-render` command or flag missing from it,
names a Sulu MCP tool that does not exist, or names a next-release tool
without saying so.
