# Sulu render API reference

Base URL: `https://api.superlumin.al`.

Use a normal Sulu user token in `Authorization` for `/api` routes.
Farm passthrough routes instead use the organization-scoped render queue
`user_key` in `Auth-Token`. Direct object storage transfers use temporary project-storage
credentials. Never mix or expose these credentials.

## Contents

- [Submission](#submission)
- [Jobs API](#jobs-api)
- [Farm control](#farm-control)
- [Capacity and pricing](#capacity-and-pricing)
- [Settings schemas](#settings-schemas)
- [Collections](#collections)
- [Error handling](#error-handling)
- [Excluded surfaces](#excluded-surfaces)

## Submission

### POST /api/farm/{org_id}/jobs

Registers a render job and can immediately create billable GPU work.

The route accepts no idempotency key. The client must:

- authenticate a normal user;
- prove the user can access the organization and project;
- use a fresh UUID;
- verify uploaded inputs;
- obtain explicit human approval for scope and estimated cost;
- send one request;
- reconcile the UUID instead of retrying.

The request is an object with `job_data` or `jobData`. `tasks` normally lives
inside that object. Any client-supplied `operations` are discarded and rebuilt
by the service.

Important fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | string | yes | Fresh client-generated UUID. |
| `project_id` | string | yes | Project record ID or project short ID within the organization. |
| `input_job_id` | string | no | Uploaded input root; defaults to `id`. |
| `blender_version` | string | yes | Supported Sulu Blender toolchain key. |
| `project_path` | string | yes | Project storage prefix. |
| `main_file` | string | yes | Relative scene path. |
| `tasks` | integer array | yes | Ordered task/frame identifiers. |
| `batch_size` | integer | no | Positive; changes task-to-frame mapping. |
| `zip` | boolean | no | Selects archive versus project input mode. |
| `packed_addons` | string array | no | Uploaded add-on bundle identifiers. |
| `image_format` | string | no | Requested output format. |
| `use_scene_image_format` | boolean | no | When true, scene output settings win. |
| `render_engine` | string | no | Blender engine identifier. |
| `render_order` | string | no | Supported render ordering mode. |
| `settings_overrides` | array | no | Validated setting path/value pairs. |
| `scene_metadata` | object | no | Optional editor metadata. |
| `name` | string | no | Human-readable job name. |

Do not send storage credentials, server operation graphs, costs, aggregate
counters, status, or other server-owned fields.

Success is HTTP `200` with:

```json
{"status":"success","body":{"job_id":"{jobId}"}}
```

HTTP `200` can also carry an application error. Parse the body and verify the
returned ID. A transport failure, malformed response, timeout, or server error
after dispatch is indeterminate and must not be replayed.

## Jobs API

Every route in this section requires a normal user token and organization
membership.

### GET /api/jobs/{org_id}

Lists stored jobs for the organization.

Query parameters:

- `include_deleted`: include deleted records;
- `project_id` or `project`: filter by project ID or project short ID;
- `limit`, `per_page`, or `perPage`: result limit.

The response body is a map keyed by job ID, not an ordered array.

### GET /api/jobs/{org_id}/{job_id}

Reads one stored job and is the preferred submission-reconciliation endpoint.
The response contains `job_data`, aggregate task maps, and placeholder
farm-data fields. A new job can take time to appear in this mirror.

### PATCH /api/jobs/{org_id}/{job_id}

Edits a stored non-running, non-deleted job. It does not modify live farm work.

Allowed fields:

- `name`;
- `frame_start`, `frame_end`, `frame_step`;
- `batch_size`;
- `image_format`, `use_scene_image_format`;
- `render_engine`, `render_order`;
- `ignore_errors`, `zip`, `use_bserver`, `use_async_upload`;
- `scene_metadata`;
- `settings_overrides`.

Frame-range edits regenerate tasks and reset stored progress to `queued`.
Confirm the exact requested change and patch only those fields.

### POST /api/jobs/{org_id}/{job_id}/duplicate

Creates a new billable farm job using the source job's resolved input root.
The server generates the new ID, so ambiguous outcomes are difficult to
reconcile.

Optional body fields:

- `name`;
- `edits`, using the same validation as the PATCH endpoint.

Require the same scope, cost, and human-approval checks as a fresh submission.
Call once and never retry automatically.

### GET /api/jobs/{org_id}/{job_id}/source_manifest

Discovers rendered output objects and classifies them by frame, layer, source
kind, and source resolution.

Supported query parameters:

- `frame`;
- `frame_start`, `frame_count`, `frame_step`;
- `limit`;
- `scan_limit`.

The response includes object keys, sizes, frame information, layer metadata,
and `truncated`. Only supported image formats are returned. This route can
provision missing project storage as a side effect.

### POST /api/jobs/{org_id}/{job_id}/source_urls

Presigns known output keys.

Request:

```json
{"sources":[{"frame":"{frame}","key":"{outputKey}"}]}
```

The server validates that each key belongs to an accepted output prefix and
matches the requested frame. Up to 100 sources are accepted. Returned URLs are
short-lived secrets.

### POST /api/jobs/{org_id}/{job_id}/source_resolve

Chooses the best output for a frame, optionally preferring a layer.

Request:

```json
{"frame":"{frame}","layer":"{optionalLayer}"}
```

The response reports the selected source kind, resolution, layer, size,
revision metadata, expiry, key, and presigned URL.

## Farm control

Farm passthrough routes use `Auth-Token: <user_key>`. Read the key only from
the authorized organization's `render_queues` record and keep it in protected
memory.

Common routes:

| Purpose | Request | Body |
| --- | --- | --- |
| Live job/task state | `GET /farm/{org_id}/api/job_list` | none |
| Pause or resume | `POST /farm/{org_id}/api/job_status` | `job_id`, target `status` |
| Delete job | `POST /farm/{org_id}/api/delete_job` | `job_id` |
| Read summary | `GET /farm/{org_id}/api/summary` | none |
| Read active machines | `GET /farm/{org_id}/api/active_machines` | optional machine ID |
| Read task logs | `GET /farm/{org_id}/api/logs` | job, task, and machine selectors |

Use these only when the authenticated jobs API lacks the needed live detail.
Pause, resume, and delete affect real work and require explicit confirmation.
Deletion is irreversible.

Do not use admin-key operations such as node registration, heartbeats, or log
deletion.

## Capacity and pricing

### GET /api/render/capacity/{organization_id}

Returns the organization capacity snapshot and pricing estimate inputs:

- `revision`;
- requested, administrative, usable, running, pending, target, and preview GPU
  counts;
- requested and effective GPUs per node;
- `shape_change_pending`;
- rate-table and current-rate fields;
- pricing multiplier and curve identity;
- snapshot timestamp;
- `estimate`.

Validate organization identity, snapshot freshness, revision, GPU shape, and
rate-table consistency before quoting a render.

Billing uses node wall-clock duration, effective GPUs per node, and the
concurrency rate. Transfer overhead therefore contributes to cost.

Use the most expensive applicable rate within the manager's plausible
concurrency bound and a conservative runtime assumption:

```text
frames × minutes per frame ÷ 60
× effective GPUs per node × rate in micro-USD ÷ 1,000,000
```

Add contingency and compare against the current balance. The result is not a
hard spend limit.

### PUT /api/render/capacity/{organization_id}

Changes requested capacity.

Strict request fields:

```json
{
  "requested_max_gpus": 0,
  "gpus_per_node": 1,
  "expected_revision": 0
}
```

Send only fields the human approved, using the revision from a fresh GET.
Increasing capacity while work is queued can increase billable allocation.

## Settings schemas

### GET /api/blender_schemas/{schema_key}

Reads a settings schema for a supported Blender toolchain key. This is a public
read and returns the stored schema JSON.

### POST /api/blender_schemas

Reads a schema by request body for compatibility with the web client. Treat it
as a read-style operation even though it uses POST.

Do not infer unsupported setting paths. Use the returned schema when building
`settings_overrides`.

## Collections

### render_queues

Organization owners can read queue records. Important fields include:

- `organization`;
- `user_key`;
- administrative and node keys;
- queue and deployment metadata.

Use only `user_key` for documented farm passthrough operations. Treat every
key as a secret. Do not expose administrative or node credentials.

Other domain records are intentionally accessed through custom routes:

- jobs through `/api/jobs`;
- project storage through `project_storage`;
- organization balance through organization/job responses;
- settings schemas through `/api/blender_schemas`.

## Error handling

Response shapes differ:

- jobs routes use the Sulu success envelope and Sulu-style errors;
- capacity routes use an `error` object with a code and retryable flag;
- farm submission and duplication can return
  `FARM_UPSTREAM_UNAVAILABLE`;
- farm passthrough routes can return farm-native responses.

Rules:

- Parse application status, not only HTTP status.
- Preserve the exact submitted UUID for reconciliation.
- Retry only idempotent reads with bounded backoff.
- Honor `Retry-After`.
- Never replay submit, duplicate, control, delete, or capacity writes after an
  ambiguous outcome.
- Redact credentials, signed URLs, and upstream error bodies.

## Scope boundary

Use only the public routes documented in this skill. Do not discover or call
privileged, diagnostic, machine-control, repair, or service-only operations.
Stay inside the authenticated account and stop at authorization boundaries.
