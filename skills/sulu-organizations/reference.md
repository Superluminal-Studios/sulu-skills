# sulu-organizations reference

Complete endpoint and collection reference for organizations, membership, and projects.
Base URL: `https://api.superlumin.al`. Auth header on every authenticated call:
`Authorization: <token>` (raw Sulu JWT; a `Bearer` prefix is tolerated).

See the [task-oriented guide](SKILL.md) and
[shared guardrails](../../GUARDRAILS.md) for conduct rules.

## Contents

- [Conventions in this domain](#conventions-in-this-domain)
- [Organization routes](#organization-routes)
- [Projects](#projects-Sulu-records-api)
- [Collections](#collections)
- [Flows](#flows)
- [Gotchas](#gotchas)

## Conventions in this domain

- **Response shape.** The `/api/organizations*` routes return their JSON payload directly.
  They do **not** wrap it in the `{"status":"success","body":{...}}` envelope that some other
  Sulu custom public routes use. Sulu record endpoints return the standard record or list
  shape (`{page, perPage, totalItems, items}`).
- **Errors** are Sulu-shaped: `{"status":<code>,"message":"<text>","data":{}}`.
- **Auth levels used below:**
  - *public*: no token.
  - *user-token*: a normal signed-in user token.
  - *org-member*: user-token plus you are `organizations.owner_id` (resolved role `owner`) or
    have an `organization_members` row for that org with `status` empty or `active`.
  - *owner*: user-token plus you are `organizations.owner_id`. The `admin` role is **not**
    sufficient for mutations.
  - *seller-capability*: user-token plus a seller capability check (owner, or an active
    member with a seller `roleKey`).
- **Strict JSON decoding** on the organization mutation routes: body must be at most 64 KiB,
  exactly one JSON value, and contain no unknown fields. Server-owned fields such as
  `balance` or `seller_verified` are rejected with 400, not silently ignored.
- **Ids** in examples (`org_abc123`, `usr_def456`) are placeholders. Real Sulu ids are
  15-character lowercase alphanumeric strings.

## Organization routes

### GET /api/organizations/public

- **Auth:** public.
- **Purpose:** batch-resolve public seller identities (name plus avatar) for marketplace
  display.
- **Query:** `ids` (required) comma-separated organization ids, max 100 entries, each at most
  64 characters. Duplicates are skipped silently.
- **Response 200:** `{"items":[{"id","name","avatar"}]}`. Exactly those three fields.
  Organizations that are not public sellers are omitted silently (they must be active,
  `seller_enabled`, `seller_verified`, not platform-suspended, not admin-restricted).
  `avatar` is a `/api/files/organizations/{id}/{filename}` URL only when
  `seller_avatar_validated` is true, otherwise `""`.
- **Errors:** 400 `ids is required`, `too many organization ids`, `organization id is
  invalid`; 500 on service failure.
- **Side effects:** none.
- **Note:** this is for rendering seller cards you already have ids for. It is not a
  directory, and it is not a way to enumerate organizations.

```http
GET /api/organizations/public?ids=org_abc123%2Corg_xyz789
```

### GET /api/organizations

- **Auth:** user-token.
- **Purpose:** list the organizations the caller owns or belongs to. This is the only
  supported way to discover org ids.
- **Query:** none. No pagination.
- **Response 200:** `{"items":[<summary DTO>],"totalItems":<n>}`.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | The `org_id` other skills need |
| `name` | string | |
| `description` | string | |
| `color` | string | `#rrggbb` or `""` |
| `avatar` | string | File URL or `""` |
| `owner_id` | string | User id of the owner |
| `role` | string | Omitted when empty. `"owner"` for owned orgs, else the resolved member role name |
| `is_owner` | bool | |
| `created`, `updated` | string | Omitted when empty |

- Filtered out: orgs with no owner, `archived`, or `ownership_state` other than `""`/`active`;
  memberships whose `status` is not active. Sorted owners first, then by name, then id.
- **Errors:** 409 `organization count exceeds the supported limit` (owning more than 50 orgs);
  409 `organization membership count exceeds the supported limit` (more than 200 membership
  rows); 500 on service errors.
- **Side effects:** none.

### POST /api/organizations

- **Auth:** user-token. Creates an org owned by the caller.
- **Consequence:** provisions render-queue infrastructure asynchronously. Confirm with the
  human before calling.
- **Body** (`organizationGeneralMutation`):

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | yes | Trimmed, at most 120 runes |
| `description` | string | no | At most 2000 runes |
| `color` | string | no | `#rrggbb` hex (normalized to lowercase) or `""` |
| `avatar` | string | no | Only `""` is accepted. Any non-empty value returns 400 `avatar must be uploaded through the seller profile endpoint` |

- **Response 201:** the detail DTO for the new organization.
- **Errors:** 400 invalid body or validation message; 409 `organization limit reached` at 50
  owned orgs (checked inside the transaction).
- **Side effects:**
  - Sets `owner_id` to the caller and `ownership_state` to `active`.
  - Assigns public identifiers and default settings.
  - Ensures the owner's membership.
  - Begins provisioning the organization's render capacity.

```http
POST /api/organizations
```

### GET /api/organizations/{orgId}

- **Auth:** org-member.
- **Purpose:** fetch one organization with role-scoped account detail.
- **Response 200:** the detail DTO = the summary fields above plus:

| Field | Type | Visible to |
| --- | --- | --- |
| `balance` | float | every member (shared render-credit balance) |
| `max_node_count` | int | owner, or member whose role name is exactly `admin` |
| `pricing_tier_id` | string | owner or `admin` member |
| `has_customer` | bool | owner or `admin` member |

- Server authority fields (`customer_id`, `stripe_connect_account_id`, `seller_verified`,
  moderation flags) are never serialized.
- **Errors:** 400 `organization id is invalid` (empty or longer than 64 characters); 404
  `organization not found` (also returned for archived or quarantined orgs); 403 `not a
  member of this organization`.
- **Side effects:** none.

### PATCH /api/organizations/{orgId}

- **Auth:** **owner only.** A member with the `admin` role gets 403 `only the organization
  owner can update general settings`. Access is re-resolved inside the write transaction.
- **Body:** same shape as POST, but `name` is optional and at least one of
  `name`/`description`/`color`/`avatar` is required (otherwise 400 `at least one organization
  field is required`). Unknown fields return 400. `avatar` accepts only `""`, which clears
  `avatar`, `seller_avatar`, and `seller_avatar_validated`.
- **Response 200:** a fresh detail DTO.
- **Side effects:** updates the named organization fields.

```http
PATCH /api/organizations/org_abc123
```

### DELETE /api/organizations/{orgId}

- **Auth:** owner only. A non-owner member gets 403 `only the organization owner can manage
  it`.
- **Behavior:** **always refuses.** After the ownership check it returns 409 `organizations
  cannot be deleted; contact support to archive this organization`.
- **Side effects:** none. Nothing is deleted.
- There is no soft delete and no archive endpoint for users. Archival is an operator action.
  Do not advise "delete and recreate", and do not delete the org's projects as a substitute:
  that destroys rendered output while leaving the organization in place.

### GET /api/files/organizations/{orgId}/{filename}

- **Auth:** public, standard Sulu file serving, but a download automation returns **404
  unless** the field is `seller_avatar` and the record has `seller_avatar_validated = true`.
  This is the URL emitted in `avatar` DTO fields.

### Seller profile routes (handled here, documented in sulu-market-seller)

Two organization-shaped routes belong to the seller domain. Full field reference is in the
[seller guide](../sulu-market-seller/SKILL.md).

- `GET /api/market/seller/{orgId}/profile` (seller-capability `seller_access`): returns `id`,
  `name`, `avatar`, `slug`, `tagline`, `bio`, `website`, `location`, `social_links`,
  `verified`, `rating`, `review_count`, `total_sales`, `blender_donation_enabled`,
  `blender_donation_pct`. 404 if the org is not active.
- `PATCH /api/market/seller/{orgId}/profile` (seller-capability, gated per field group:
  identity fields need owner or `seller_admin`; tagline, bio, and avatar need owner,
  `seller_admin`, or `seller_content`; donation fields need owner, `seller_admin`, or
  `seller_finance`). Accepts strict JSON or `multipart/form-data`; the multipart form is the
  only way to upload an avatar (PNG/JPEG/WebP, at most 2 MiB, 16 to 4096 px per side).
  This changes the public seller profile.
- Public seller identity changes reach other people. Draft, confirm, then send.

## Projects (Sulu records API)

Projects use the public records API.

### GET /api/collections/projects/records

- **Auth:** user-token. Lists and views return only projects owned by the
  signed-in user.
- **Useful query params:** `filter`, `sort`, `page`, `perPage`, `skipTotal=true`, `fields`,
  `expand`.

```http
GET /api/collections/projects/records?filter=%28organization_id%3D%27org_abc123%27%20%26%26%20archived%3Dfalse%29&sort=-updated&perPage=50&skipTotal=1
```

### POST /api/collections/projects/records

- **Auth:** user-token. Set `owner_id` to the signed-in user's id.
- **Consequence:** provisions project storage and temporary storage access.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | text | Also used as `project_path` when submitting renders |
| `description` | text | |
| `owner_id` | relation to `users` | Set this to your own user id |
| `organization_id` | relation to `organizations` | **Server-derived.** Omit it on create; the automation chooses the owner's first organization. |
| `color` | text | |
| `avatar`, `banner`, `poster` | file | One file each |
| `key` | text | `^[a-z0-9_]+$`, at most 50 chars, unique per `(organization_id, key)` when non-empty |
| `settings` | json | Treat as opaque unless another public guide defines it |
| `archived` | bool | Use this instead of deleting |
| `rootElement` | relation to `elements` | Server-derived after project setup; omit it on create. |
| `data`, `farm_data` | json | Treat as opaque unless another public guide defines them |
| `sqid` | text | **Server-assigned.** Short id used in web URLs; the render submit route accepts it in place of the record id |

- **Service effects:** assigns `sqid`, associates the project with the owner's
  organization, provisions project storage, and ensures the owner's membership.
  Re-read the created project and storage record rather than predicting
  service-assigned values.

### PATCH /api/collections/projects/records/{id}

- **Auth:** owner only. Use this to rename, recolor, or set `archived: true`.
- **Agent API limit:** PATCH only the requested ordinary scalar field. Agent
  API policy rejects `owner_id`, `organization`, `organization_id`, `rootElement`,
  and server-assigned `sqid`. Do not use a raw request to evade this boundary.

### DELETE /api/collections/projects/records/{id}

- **Auth:** owner only.
- **Consequence: irreversible data destruction.** This deletes linked project
  storage, including rendered frames, and related storage records. There is no
  undo. Name the project to the human and get an explicit yes first, and
  offer `archived: true` as the non-destructive alternative.

## Collections

### organizations

Do not access this collection through the records API. Use the
`/api/organizations` routes. Fields
include `owner_id`, `name`, `description`, `color`, legacy `avatar` (never serialized),
`sqid`, `slug`, `settings`, `archived`, `ownership_state`
(`active` / `pending_ownerless_quarantine` / `quarantined_ownerless`), `balance`,
`max_node_count`, `pricing_tier_id`, `customer_id`, and the `seller_*` and
`stripe_connect_*` fields.

### organization_members

- **Read:** organization owners and members may read membership rows.
- **Writes:** unavailable through the user API. **There is no API to invite,
  add, remove, or re-role a member.** The
  `status` value `invited` exists in the schema but no code path sets it, and no
  member-management HTTP endpoints exist in this domain.
- **Fields:** `user_id`, `organization_id`, `project_id`, `department_id`, `role` (relation to
  `roles`), `roleKey` (text; wins over `role` when set), `permissions` (json; no reader found,
  treat as unused), `status` (`invited` / `active` / `suspended`; empty counts as active),
  `meta`. Unique index on `(organization_id, user_id)`.

```http
GET /api/collections/organization_members/records?filter=%28organization_id%3D%27org_abc123%27%29&expand=user_id%2Crole&skipTotal=1
```

`expand=user_id` resolves only the signed-in user's row, so every other member
comes back as a bare user id with nothing in `expand`. `expand=role`
works for all rows.

Reading membership tells you who has access. Changing it is out of reach: direct the human to
the Sulu app or support.

### roles

- **List and view:** any authenticated user. **Writes:** unavailable.
- Seeded rows: `admin`, `manager`, `editor`, `viewer`. Only `admin` has server-side meaning in
  this domain: it unlocks the owner-level fields on the org detail DTO. It does **not** grant
  `PATCH` or `DELETE` on the organization. Seller roles are `roleKey` strings
  (`seller_admin`, `seller_content`, `seller_finance`, `seller_support`), not `roles` rows.

### project_storage

- **Read:** members of the project's organization. **Writes:** unavailable.
- **Fields:** `project_id`, `bucket_name`, `access_key_id`, `secret_access_key`,
  `session_token`, `expiry`.
- These are **live S3 credentials** with a one-week TTL. Never print, log, or persist them.
  Usage is covered in [../sulu-storage/SKILL.md](../sulu-storage/SKILL.md).

### Production tracker collections

`elements`, `tasks`, `task_types`, `task_schemas`, `workflows`, `workflow_statuses`,
`element_links`, `comments`, `task_versions`, `production_boards`, `production_screenplays`,
`production_cuts`, `playlists`, `playlist_items`.

Access requires authentication and membership in the record's project
organization.

- **elements**: production-hierarchy nodes (sequences, shots, assets). Fields: `project`,
  `element_type_id`, `parent_element_id`, `name`, `description`, `color`, `code`, `sort`,
  `path`, `depth`, `taskSchemaOverride`, `thumbnail`, `frameIn`, `frameOut`, `fps`,
  `stepping`, `resolutionWidth`, `resolutionHeight`, `tags`, `archived`, `meta`.
  `path` and `depth` are **server-computed from `parent_element_id`**: never send them.
  Reparenting rewrites all descendant paths after the save (best effort, failures only
  logged). After create, default tasks are seeded from the element type's `defaultTaskSchema`;
  a broken schema silently skips entries, so missing seeded tasks is not an API error.
- **tasks**: per-element work items. Fields: `project`, `element`, `taskType`, `key`, `title`,
  `workflow`, `status`, `assignees`, `departmentLock`, `priority`, `tags`, `estimation`,
  `startDate`, `endDate`, `dueDate`, `retakeCount`, `lastActivityAt`, `archived`, `meta`.

## Flows

### 1. Sign-up to default organization (server-driven, no client calls)

1. A `users` record is created by password sign-up or OAuth.
2. `ensureDefaultOrg` creates an org named `"<Display Name>'s Studio"` owned by that user
   (idempotent; also backfilled after every login) and ensures the owner's
   `organization_members` row with the `admin` role.
3. The service applies defaults and begins render-capacity provisioning.

A fresh account therefore always has exactly one owned org, one admin membership row, and
render queue keys. There is no "create my first org" step for a new user.

### 2. Client boot: enumerate and pick

1. `POST /api/collections/users/auth-refresh` for your user id.
2. `GET /api/organizations`, pick an org id (`is_owner` and `role` tell you what you can do).
3. `GET /api/organizations/{orgId}` for `balance`, plus the owner-only account fields.

### 3. Create an extra organization

1. Confirm with the human, then `POST /api/organizations`.
2. The 201 body already carries `pricing_tier_id` and `max_node_count`. The render queues are
   spawned in the background and never appear in an organization DTO, so there is nothing to
   re-fetch for them either.

### 4. Update settings (owner)

`PATCH /api/organizations/{orgId}` with any subset of `name`, `description`, `color`,
`avatar:""`. The response is a fresh detail DTO and an audit row is written.

### 5. Create a project and reach its storage

1. `POST /api/collections/projects/records` with `{name, owner_id: "<your-user-id>"}`.
2. Re-fetch the record for the assigned `sqid` and the forced `organization_id`.
3. `GET /api/collections/project_storage/records?filter=project_id="<projectId>"` for
   `bucket_name` and the temporary S3 credentials.

### 6. Build a production hierarchy

1. Create `elements` records (`project`, `name`, optional `parent_element_id`,
   `element_type_id`). The server fills `path` and `depth`.
2. If the element type has a `defaultTaskSchema`, `tasks` appear automatically; list them with
   `filter=element="<elementId>"`.
3. Reparenting an element rewrites descendant paths server-side.

### 7. Marketplace display of seller orgs (anonymous)

`GET /api/organizations/public?ids=a,b,c` returns only verified, unsuspended sellers. Use
`name` and `avatar` directly.

## Gotchas

- `DELETE /api/organizations/{orgId}` always returns 409. There is no org deletion path.
- Deleting a project is infrastructure teardown: object storage buckets and rendered frames go with it.
- `GET /api/organizations` returns 409 for users owning more than 50 orgs or holding more than
  200 membership rows.
- The org detail's extra fields need role name exactly `admin`; org mutations need
  *ownership*, which is a different check.
- Use a normal signed-in user token.
- A project's `organization_id` is force-set to the owner's first org, so a
  multi-org owner cannot place a project in a chosen org through the records API.
- Project list and view rules are owner-only, so `GET /api/collections/projects/records` is
  not an inventory of the organization's projects, only of yours.
- Avatar handling is split: the general org routes can only clear an avatar; uploads go
  through the multipart seller-profile route; serving is 404-gated on
  `seller_avatar_validated`.
- Render capacity may take a short time to appear after organization creation.
- Listing `projects` or `project_storage` without an explicit `skipTotal` param gets
  `skipTotal=1` forced on by a server middleware, so `totalItems` and `totalPages` come back as
  `-1`. Pass `skipTotal=false` if you actually need a count.
- Deleting your own account changes **every organization you own**:
  `ownership_state` becomes `quarantined_ownerless`, `archived` true, `seller_enabled` false,
  `seller_admin_restricted` true. That is account deletion, not organization deletion, and it
  is not a way around the 409 above. Never call it as a workaround.
