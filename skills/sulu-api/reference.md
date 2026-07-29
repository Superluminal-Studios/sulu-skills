# sulu-api reference

Complete reference for authentication, identity, and the Sulu records API on
`https://api.superlumin.al`.

## Contents

- [Authentication endpoints](#authentication-endpoints)
- [Token mechanics](#token-mechanics)
- [The records API](#the-records-api)
- [Realtime subscriptions](#realtime-subscriptions)
- [Gotchas](#gotchas)

## Authentication endpoints

### POST /api/collections/users/auth-with-password

- **Auth**: public.
- **Purpose**: email and password sign-in for the `users` collection.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `identity` | string | yes | The email address. Email is the only identity field. |
| `password` | string | yes | |

**Response**: `{"token": "<jwt>", "record": {...}}`. The record carries `id`, `email`,
`emailVisibility`, `verified`, `display_name`, `user_name`, `description`, `avatar`,
`prefs`, `created`, `updated`.

**Errors**: `400` wrong credentials or validation failure. `403` the account is not
email-verified (the collection's auth rule is `verified = true`), which the web app treats
as a prompt to resend verification.

**Side effects**: the service may create a default organization named
`"<display name>'s Studio"` plus an owner membership row, if the account has none.

### POST /api/collections/users/auth-refresh

- **Auth**: user token.
- **Purpose**: exchange a valid token for a fresh one and read the current user record.
  This doubles as the canonical "who am I" call.

**Request**: no body. **Response**: `{"token": "<new jwt>", "record": {...}}`.

**Errors**: `401` missing, invalid, or expired token. `403` the account no longer satisfies
the auth rule.

The previous token stays valid until its own expiry: refreshing does not revoke it. There
is no server-side token revocation short of a password or email change, either of which
rotates the signing key for that user and invalidates every token issued to them.

### Account signup

Account creation requires interactive human verification and email
verification. Direct the human to `https://superlumin.al`; do not attempt to
automate signup through the records API.

### POST /api/collections/users/request-verification

- **Auth**: public. **Request**: `{"email": "user@example.com"}`.

Sends the verification email. The web app calls this after signup and whenever a login
returns `403`.

### POST /api/cli/start (device link, step 1)

- **Auth**: public.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `device_hint` | string | no | Free-form label shown to the approving human. |
| `scope` | string | no | Stored verbatim. No scope semantics are enforced server-side. |

**Response**:

```json
{
  "txn": "<43-char base64url handle>",
  "user_code": "ABCD-2346",
  "verification_uri": "https://superlumin.al/link",
  "verification_uri_complete": "https://superlumin.al/link?txn=<txn>",
  "interval": 2,
  "expires_in": 479
}
```

The `user_code` is eight characters formatted `XXXX-XXXX`, and its alphabet excludes `I`,
`O`, `S`, `0`, `1`, and `5` to avoid transcription errors. Links expire after 8 minutes, so
`expires_in` comes back as 479 rather than a clean 480. Each call writes a temporary authorization record, so
do not call it repeatedly: expired rows are garbage-collected every 10 minutes.

### POST /api/cli/approve (device link, step 2)

- **Auth**: any authenticated record, normally a browser session.
- **Request**: `{"txn": "..."}` or `{"user_code": "ABCD-2346"}` (upper-cased before the
  lookup, so lowercase input works). One of the two is required.
- **Response**: `204 No Content`.
- **Errors**: `400` neither field supplied. `404 invalid or expired link`, which also
  covers already-approved links. `401` unauthenticated.

**Agents must not call this.** Approving a handle hands a 7-day token for the approving
account to whoever holds the `txn`. It is the human's step, performed in their browser at
`https://superlumin.al/link`.

### POST /api/cli/token (device link, step 3)

- **Auth**: public. Possession of the `txn` is the credential.
- **Request**: `{"txn": "..."}`.

| Status | Meaning |
| --- | --- |
| `428` | Not approved yet. Header `Retry-After: 2`. Keep polling at that interval. |
| `200` | `{"token": "<jwt>", "record": {...}}`. The link row is deleted first: strictly single use. |
| `400 missing txn` | Malformed request. |
| `400 expired_token` | The link expired and was deleted. Restart from step 1. |
| `404 invalid txn` | Unknown handle. |
| `403` | The approving account is not verified. The link was already consumed, so restart. |

Treat anything other than `428` and `200` as terminal.

## Token mechanics

| Property | Value |
| --- | --- |
| Format | Stateless JWT |
| Header | `Authorization: <token>` (a `Bearer ` prefix is tolerated) |
| Lifetime | 604800 seconds (7 days) |
| Refresh | `POST /api/collections/users/auth-refresh` |
| Revocation | None per-token. A password or email change invalidates all of that user's tokens. |
| Verification token | 259200 seconds (3 days) |
| Password reset token | 1800 seconds |

MFA and one-time codes are disabled. OAuth2 is enabled for Google and Discord, which is a
browser flow and not usable headlessly.

## The records API

`GET /api/collections/{collection}/records` with standard Sulu query parameters:

| Param | Purpose |
| --- | --- |
| `filter` | Filter expression, e.g. `(organization_id='org_abc123' && status='active')` |
| `sort` | Comma-separated fields, `-` prefix for descending |
| `expand` | Inline related records by relation field name |
| `fields` | Restrict returned fields |
| `page` / `perPage` | Pagination, `perPage` capped at 1000 |
| `skipTotal` | Skip the count query, returning `totalItems: -1` |

Single record: `GET /api/collections/{collection}/records/{id}`. Writes use `POST`,
`PATCH`, and `DELETE` on the same paths, subject to each collection's rules.

Canonical method/path spellings:

- `GET /api/collections/{collection}/records`
- `GET /api/collections/{collection}/records/{id}`
- `POST /api/collections/{collection}/records`
- `PATCH /api/collections/{collection}/records/{id}`
- `DELETE /api/collections/{collection}/records/{id}`
- `GET /api/files/{collection}/{recordId}/{filename}`
- `POST /api/files/token`

`POST /api/files/token` returns a protected-file bearer token for the signed-in
auth record. Treat it as a secret and pass it in memory to an immediate
Sulu file consumer that can add the protected-file query internally;
never print, log, or place it in a command argument or caller-visible URL.

Do not turn generic route templates into generic authority. Use a records
operation only when the public inventory lists the collection and its owning
domain skill authorizes that operation. Never use raw
writes for `render_queues`, `referrals`, or `referral_usages`, never exploit
undocumented create behavior, and never guess an unlisted collection.

For PATCH, change only fields the owning domain skill explicitly marks
writable. Keep tenant anchors, relation-integrity fields, provenance,
annotation identity, and service-maintained fields unchanged. For POST,
read every referenced record and prove same-organization, same-project, and
workflow/task/version coherence before creating the record. Creates must also
omit service-derived fields such as project `sqid` and
organization/root, element `path`/`depth`, task head, version revision/head
flags, and comment resolution state. Re-read the created result.

### Forced skipTotal

The API applies `skipTotal=1` to list queries for these six collections unless
the caller explicitly sends a `skipTotal` value:

`pricing_tiers`, `project_storage`, `projects`, `referrals`, `referral_usages`,
`render_queues`

For those, `totalItems` and `totalPages` are `-1`. Page until you receive a short page, or
pass `skipTotal=0` when you truly need a count. A known real-world bug caused by this: a
client that paginated on `totalPages` silently stopped after the first 100 projects.

This behavior applies only to collection-list requests.

### Collection access

| Collection | Access |
| --- | --- |
| `users` | List is public (emails hidden unless `emailVisibility` is set). View, update, and delete are self-only. Create is public, Turnstile-gated. |
| `projects` | The signed-in owner may list, view, update, and delete their projects. Creating a project can provision storage. See [sulu-organizations](../sulu-organizations/SKILL.md). |
| `project_storage` | List and view for org members. Create, update, and delete are service-only. **Reading has side effects**: it returns live credentials, rotates them when they are missing or within an hour of expiry (or when `force_renew=1`/`renew=1` is passed), and a list filtered by `project_id` that matches nothing can provision a bucket. |
| `render_queues` | Organization-owner read access. Contains a sensitive farm user key; use only where the render guide requires it. |
| `blender_settings_schemas` | Reached through `/api/blender_schemas`, not directly. |
| `organizations`, `organization_members` | See [sulu-organizations](../sulu-organizations/SKILL.md). |
| `jobs` | Read through `/api/jobs/{org_id}`. See [sulu-render](../sulu-render/SKILL.md). |
| `referrals`, `referral_usages` | See [sulu-billing](../sulu-billing/SKILL.md). |

Note the asymmetry on `users`: list is public but single-record view is self-only, so a
record you can see in a list may `404` on a direct view.

## Realtime subscriptions

Sulu exposes a server-sent-events stream at `/api/realtime`. Subscriptions
return only records the signed-in user may list and view. Render job progress
is not available through this stream; poll `GET /api/jobs/{org_id}` at
10 seconds or slower.

The flow, for the collections that do permit it:

1. `GET /api/realtime` opens the SSE stream. The first event is `PB_CONNECT`, whose data is
   `{"clientId": "..."}`.
2. `POST /api/realtime` with the client id and your topics, sending the auth token:

```http
POST /api/realtime
```

Returns `204`. A topic may carry query options after `?`, for example
`tasks?filter=project="proj_abc123"`. Changing the auth token means re-submitting the
subscriptions.

Open the long-lived SSE `GET` with a Sulu/SSE client that reads the token from
protected runtime state. Never place the token in a command argument or log the
event-stream headers.

Prefer polling unless you have a specific collection that both permits subscription and
changes often enough to justify holding a stream open.

## Gotchas

- **Signup does not sign you in**, and the account cannot authenticate until verified. A
  `403` on login means unverified, not "wrong password".
- **Device links are single-use and expire in 8 minutes.** The row is deleted on the first
  successful exchange and on expiry detection.
- **Poll at the interval the server gives you.** `/api/cli/token` returns `Retry-After: 2`.
  Do not tighten it.
- **`/api/cli/start` is unauthenticated and writes a row per call.** Do not retry it in a
  loop.
- **Never log tokens**, and never write them into files that get committed.
- **Request bodies are transient input.** Keep secret-bearing bodies in protected
  runtime state and reject credential or capability query arguments.
- **Reading `project_storage` returns live cloud credentials** and can mutate state. Fetch
  it only when you are about to transfer files.
- **Chatwoot widget GETs can mutate.** They may repair the account's contact
  mapping or refresh its widget token, so call them deliberately. Permit no
  conversation-list query and only one numeric `before` cursor for messages.
