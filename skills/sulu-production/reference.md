# Sulu production API reference

Complete method, access, and schema inventory for the user-accessible production
tracker. Base URL: `https://api.superlumin.al`. Send
`Authorization: <user-token>` on every request. See
[SKILL.md](SKILL.md) for the safe operating procedure.

## Contents

- [Record endpoints](#record-endpoints)
- [Effective rules](#effective-rules)
- [Safe update boundary](#safe-update-boundary)
- [Complete field inventory](#complete-field-inventory)
- [Relation and naming traps](#relation-and-naming-traps)
- [Common filters](#common-filters)
- [Files](#files)
- [Domain references](#domain-references)
- [Off-limits](#off-limits)

## Record endpoints

Every collection below uses the same Sulu endpoint family:

| Purpose | Request |
| --- | --- |
| List | `GET /api/collections/{collection}/records` |
| View one | `GET /api/collections/{collection}/records/{recordId}` |
| Create | `POST /api/collections/{collection}/records` |
| Update | `PATCH /api/collections/{collection}/records/{recordId}` |
| Delete | `DELETE /api/collections/{collection}/records/{recordId}` |

JSON is appropriate unless uploading a file. Lists accept `filter`, `sort`,
`expand`, `fields`, `page`, `perPage`, and `skipTotal`. Record responses are
Sulu records; lists are `{page, perPage, totalItems, totalPages, items}`.
Errors are Sulu-shaped and writes have no idempotency key.

## Access model

“Member” below means the signed-in user has organization membership for the
selected project. Owners are included.

| Collection | Rule anchor | List/view | Create/update/delete |
| --- | --- | --- | --- |
| `departments` | `org` → organization membership | Member | Member |
| `project_presets` | optional `org` | Any authenticated user for `org=""`; member for org rows | Member, and `org` must resolve to a member org |
| `workflows` | `project` | Project-org member | Project-org member |
| `workflow_statuses` | `workflow.project` | Project-org member | Project-org member |
| `task_types` | `project` | Project-org member | Project-org member |
| `task_schemas` | `project` | Project-org member | Project-org member |
| `element_types` | legacy `project_id` | Project-org member | Project-org member |
| `elements` | `project` | Project-org member | Project-org member |
| `element_links` | `project` | Project-org member | Project-org member |
| `tasks` | `project` | Project-org member | Project-org member |
| `task_versions` | `task.project` | Project-org member | Project-org member |
| `comments` | `task.project` | Project-org member | Project-org member |
| `time_logs` | `task.project` | Project-org member | Project-org member; writes must retain the signed-in user |
| `notifications` | `user` | Recipient | Create denied; recipient update/delete |
| `playlists` | `project` | Project-org member | Project-org member |
| `playlist_items` | `playlist.project` | Project-org member | Project-org member |
| `production_boards` | `project` | Project-org member | Project-org member |
| `production_screenplays` | `project` | Project-org member | Project-org member |
| `production_cuts` | `project` | Project-org member | Project-org member |
| `media_annotations` | `project` | Project-org member | Project-org member |

For creates, confirm every submitted relation belongs to the selected project
and organization. For updates, retain tenant anchors, actor fields, and related
record identities unless this guide explicitly documents the transition.

Always cross-check every relation on create, set provenance fields to the
caller, and follow the update boundary below.

## Safe update boundary

Agent API policy rejects protected relation and server-managed PATCH fields.
A GET response is not a PATCH template: omit
relations and server-managed fields even when their values would be unchanged.
Do not bypass a rejection with raw HTTP, another client, Sulu `+`/`-`
modifiers, or a delete/recreate substitute.

| Record family | PATCH boundary |
| --- | --- |
| Configuration | Keep `departments.org`, `project_presets.org`, `workflows.project`, `workflow_statuses.workflow`, `task_types.project/defaultDepartment/defaultWorkflow`, `task_schemas.project`, and `element_types.project_id/parent_element_id/defaultTaskSchema` unchanged. Relation changes are temporarily unavailable. |
| Elements and links | Keep every element/link relation unchanged. Never send `elements.path` or `elements.depth`; both are server-managed. Element reparenting is unavailable. |
| Tasks | Keep `project`, `element`, `taskType`, `workflow`, `status`, `assignees`, `departmentLock`, and server-managed `headVersion` unchanged. Status, assignment, workflow, department, element, and type changes are temporarily unavailable. |
| Revisions | Keep `task`, `parent`, `createdBy`, `rev`, and `isHead` unchanged. `rev`/`isHead` are server-managed; head repair is temporarily unavailable. |
| Comments | Keep `task`, `version`, `parent`, `annotation`, `createdBy`, `mentions`, `isResolved`, `resolvedBy`, and `resolvedAt` unchanged. Existing-comment mention changes and coherent resolve/reopen changes are temporarily unavailable. |
| Time logs | Keep `task` and `user` unchanged. PATCH only the caller's existing log fields such as `date`, `duration`, `note`, or `meta`. |
| Notifications | PATCH exactly `isRead` and nothing else. Creation is server-only. |
| Playlists and planning documents | Keep project, element, creator, playlist, and version relations unchanged. PATCH only requested scalar/order/content fields. |
| Media annotations | Keep `project`, `author`, `mediaKey`, `mediaRef`, `target`, frame identity, and `space` unchanged during ordinary edits. PATCH only requested `scene`, `keyframes`, or `state` content after concurrency checks; retargeting, reframing, or changing coordinate space needs a dedicated validated workflow. |

No user-facing coordinator is documented for these protected transitions.
When a request requires one, explain the limitation and stop rather than
claiming the mutation succeeded.

## Complete field inventory

`id`, `created`, and `updated` are omitted below. `*` means schema-required;
operational validation may impose more. A field appearing here does not mean it
is safe or available to PATCH; apply the boundary above.

| Collection | Fields |
| --- | --- |
| `departments` | `org*`, `key*`, `name*`, `order`, `archived` |
| `project_presets` | `org`, `key*`, `name*`, `description`, `presetJson*`, `version`, `archived` |
| `workflows` | `project*`, `key*`, `name*`, `archived`, `meta` |
| `workflow_statuses` | `workflow*`, `key*`, `name*`, `order`, `kind`, `color`, `isTerminal`, `archived`, `meta` |
| `task_types` | `project*`, `key*`, `name*`, `defaultDepartment`, `defaultWorkflow`, `archived`, `meta` |
| `task_schemas` | `project*`, `key*`, `name*`, `tasksJson*`, `archived`, `meta` |
| `element_types` | `project_id`, `parent_element_id`, `name`, `description`, `avatar`, `color`, `key`, `icon`, `archived`, `meta`, `defaultTaskSchema` |
| `elements` | `project`, `element_type_id`, `parent_element_id`, `name`, `description`, `color`, `avatar`, `code`, `sort`, `path`, `depth`, `taskSchemaOverride`, `thumbnail`, `frameIn`, `frameOut`, `fps`, `stepping`, `resolutionWidth`, `resolutionHeight`, `tags`, `archived`, `meta` |
| `element_links` | `project*`, `fromElement*`, `toElement*`, `kind*`, `roleName`, `order`, `meta` |
| `tasks` | `project*`, `element*`, `taskType*`, `key*`, `title`, `workflow*`, `status*`, `assignees`, `departmentLock`, `priority`, `tags`, `estimation`, `startDate`, `endDate`, `dueDate`, `retakeCount`, `lastActivityAt`, `headVersion`, `archived`, `meta` |
| `task_versions` | `task*`, `rev*`, `parent`, `isHead`, `message`, `createdBy*`, `mediaKind`, `originalFile`, `previewFile`, `thumbnailFile`, `textContent`, `externalUrl`, `payload`, `mimeType`, `sizeBytes`, `checksumSha256` |
| `comments` | `task*`, `version`, `parent`, `annotation`, `body*`, `createdBy*`, `mentions`, `isResolved`, `resolvedBy`, `resolvedAt`, `meta` |
| `time_logs` | `task*`, `user*`, `date*`, `duration*`, `note`, `meta` |
| `notifications` | `user*`, `kind*`, `task`, `comment`, `version`, `triggeredBy`, `isRead`, `meta` |
| `playlists` | `project*`, `name*`, `createdBy*`, `isClientPlaylist`, `archived`, `meta` |
| `playlist_items` | `playlist*`, `version*`, `order`, `note`, `meta` |
| `production_boards` | `project*`, `element*`, `name`, `scene`, `sort`, `archived`, `meta`, `createdBy` |
| `production_screenplays` | `project*`, optional `element`, `name`, `doc`, `sort`, `archived`, `meta`, `createdBy` |
| `production_cuts` | `project*`, `element*`, `name`, `doc`, `sort`, `archived`, `meta`, `createdBy` |
| `media_annotations` | `project*`, `mediaKey*`, `mediaRef*`, `target`, `frameMode*`, `frameStart`, `frameEnd`, `fps`, `space`, `scene*`, `keyframes`, `state*`, `author` |

## Relation and naming traps

| Trap | Correct behavior |
| --- | --- |
| Project relation naming | `element_types` uses `project_id`; production records otherwise use `project`; departments/presets use `org` |
| Legacy optional fields | `elements.project` and `element_types.project_id` are not schema-required, but their access rules cannot authorize an empty relation; always set them on create and omit them from PATCH |
| Screenplay scope | `production_screenplays.element` remains optional in schema even though current clients normally attach the project root/episode |
| Actor fields | `createdBy`/`author` are not bound to auth by most rules; set the caller on create, omit them from PATCH, and never impersonate |
| User expands | `users` single-record view is self-only, so `expand=createdBy,author,assignees` may omit teammate details while leaving ids |
| Cross-scope relations | The anchor rule does not prove that element/type/workflow/status/version/annotation relations agree; validate each relation |
| Protected PATCH fields | Relations are create-time inputs, not values to echo back on update; protected transitions require a documented workflow |
| Global presets | An authenticated user may read `project_presets` where `org=""`, but cannot create/update/delete a global row |

## Common filters

```text
project = "<projectId>"
project = "<projectId>" && archived != true
project_id = "<projectId>"                         # element_types only
workflow.project = "<projectId>"                  # workflow_statuses
task.project = "<projectId>"                      # versions/comments/time logs
playlist.project = "<projectId>"                  # playlist_items
task = "<taskId>"
element = "<elementId>"
annotation = "<annotationId>"
user = "<currentUserId>" && isRead = false
```

Use an SDK filter builder or URL encoding. Never insert untrusted text into a
filter expression.

## Files

Sulu file URLs use:

`GET /api/files/{collection}/{recordId}/{filename}`

The `elements.thumbnail` and all `task_versions` file fields are
`protected=false`; possession of the URL is sufficient to fetch them. Do not
upload credentials, private keys, confidential source, sensitive client media,
or anything whose public-by-URL exposure the human has not approved.

Detailed limits and multipart syntax are in
[references/review-media.md](references/review-media.md).

## Domain references

- [references/configuration.md](references/configuration.md): configuration
  fields, unique keys, setup order, task seeding
- [references/work-tracking.md](references/work-tracking.md): element/task
  invariants, links, time logs, notifications, cascades
- [references/review-media.md](references/review-media.md): revisions, file
  fields, comments, annotations, concurrency
- [references/planning.md](references/planning.md): playlists and JSON planning
  documents

## Scope boundary

Use only the documented public records operations. Do not probe another
project id or bypass protected-field guidance with a raw client or an
equivalent create/delete sequence.
