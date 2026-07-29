---
name: sulu-organizations
description: Discover and safely manage the signed-in user's Superluminal (Sulu) organizations, memberships, roles, and projects through the user-scoped API. Use for organization creation or settings, project creation or archival, membership inspection, ownership checks, and destructive project or organization requests.
---

# Sulu organizations API

Use [sulu-api](../sulu-api/SKILL.md) for authentication and shared request
rules. Follow the [shared guardrails](../../GUARDRAILS.md).

## Resolve scope

Start with:

```http
GET /api/organizations
```

This returns organizations visible to the authenticated user and their
membership or ownership context. Use only returned organization IDs.

Read one organization:

```http
GET /api/organizations/{orgId}
```

Confirm owner, membership, balance, seller state, and related metadata before
an organization-scoped action.

Public seller identity can be resolved through:

```http
GET /api/organizations/public?ids={orgIds}
```

Use it only for explicitly requested public organizations. Do not enumerate.

## Memberships and roles

Membership records are available through:

```http
GET /api/collections/organization_members/records
```

Filter by the selected organization and expand only needed user or role data.
Require an active membership when the field is present; legacy empty status is
treated according to the service compatibility rule.

Role records are available through:

```http
GET /api/collections/roles/records
```

Read roles to explain capabilities. Do not infer permissions from a role name;
use the returned capability fields and the domain endpoint's own checks.

The current user API does not provide a general safe invitation, role-change,
member-removal, or ownership-transfer workflow. Do not use raw collection
writes to invent one.

## Create an organization

```http
POST /api/organizations
```

Use the authenticated user as owner and send only documented creation fields.
Show the exact name and intended settings before creating. A create request can
trigger default role and membership records, so do not retry an ambiguous
response; re-list organizations first.

## Update organization settings

```http
PATCH /api/organizations/{orgId}
```

Only an authorized owner may update the organization. Patch only fields the
human requested, such as display or configuration settings documented by the
endpoint. Never change owner, identity, balance, Stripe state, seller state, or
server-maintained fields through this route.

Marketplace storefront settings belong to
[sulu-market-seller](../sulu-market-seller/SKILL.md), not the generic
organization PATCH.

## Projects

List accessible projects:

```http
GET /api/collections/projects/records
```

Filter by `organization_id` and request only needed fields. The current
collection read rule is owner-oriented; if the authenticated user cannot read
the project, stop rather than working around the rule.

Create:

```http
POST /api/collections/projects/records
```

Send:

- human-approved project fields;
- `owner_id` equal to the authenticated user;
- `organization_id` equal to an organization the user owns.

Omit server-derived short IDs, root elements, generated relations, and
timestamps. Re-read the record after creation to observe service-assigned values.

Update:

```http
PATCH /api/collections/projects/records/{projectId}
```

Patch only safe scalar fields such as name, description, color, or archived
state. Keep owner, organization, root element, and server-generated identity
unchanged. A legitimate move between owners or organizations requires a
dedicated service coordinator that is not currently available.

## Delete a project

```http
DELETE /api/collections/projects/records/{projectId}
```

Project deletion can cascade into production data and permanently delete the
project's object storage bucket, including source scenes and rendered output.

Before:

1. Resolve the exact project and owning organization.
2. Inventory storage, active renders, production records, and dependencies.
3. Offer an export or backup.
4. Obtain fresh confirmation naming the project.
5. Call once.

Never delete `project_storage` directly or delete a project as a storage
cleanup shortcut.

## Delete an organization

The normal user API does not expose a general organization-delete endpoint.
Do not approximate it by deleting memberships, projects, or related records.
Explain the limitation or use an explicitly documented account-deletion flow
when that is the human's actual request.

## Domain handoffs

- render and capacity: [sulu-render](../sulu-render/SKILL.md);
- project storage: [sulu-storage](../sulu-storage/SKILL.md);
- billing and balance: [sulu-billing](../sulu-billing/SKILL.md);
- seller identity and capabilities:
  [sulu-market-seller](../sulu-market-seller/SKILL.md);
- production tracker: [sulu-production](../sulu-production/SKILL.md).

## Safety boundaries

- Stay inside organizations returned for the authenticated user.
- Treat `401`, `403`, and scoped `404` responses as final boundaries.
- Authenticate every request and follow the documented project create and
  update contracts.
- Never forge ownership, membership, roles, balances, seller state, or
  server-generated IDs.
- Require explicit approval before creating or deleting durable resources.
- Do not retry ambiguous creates or deletes.

## Reference

Read the [complete organization and project reference](reference.md) for fields,
rules, automation, membership compatibility, role capabilities, cascade behavior,
and cross-domain identifiers.
