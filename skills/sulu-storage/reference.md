# sulu-storage reference

Base URL: `https://api.superlumin.al`. Auth header on every call: `Authorization: <token>` (raw
Sulu JWT; a `Bearer` prefix is tolerated). See [../sulu-api/SKILL.md](../sulu-api/SKILL.md)
for how to get a token.

Two subsystems live in this domain:

- **Per-project render storage**: the `project_storage` collection returns
  temporary S3-compatible credentials for per-project storage. There are no Sulu HTTP endpoints for
  uploading project files; clients use the S3 API directly. For reading finished frames the jobs
  API can presign individual objects (`source_manifest` / `source_urls`, below).
- **Marketplace transfer**: the `/api/storage/*` custom route group hands out presigned S3 URLs for
  public media and private product files. Clients never receive bucket credentials.

Response envelope note: some Sulu custom public routes wrap results as
`{"status":"success","body":{...}}` (the `/api/jobs/*` routes do). The `/api/storage/*` routes do
**not**: they return plain JSON objects. Their errors are
`{"error":"...","message":"...","traceId":"<uuid>"}` where `error` and `message` carry the same text
and `traceId` correlates with a server log line. One exception: the seller self-download path in
`files/download/init` rejects a missing `content_write` capability through Sulu's own error
response path, so that 403 arrives in the standard Sulu error shape, not the
`error`/`traceId` one.
Sulu records endpoints (`/api/collections/...`) use the standard Sulu error shape too.

If storage is unavailable, `/api/storage` routes return **503**.

---

## Contents

- [Project render storage](#project-render-storage)
- [Render bucket key layout](#render-bucket-key-layout)
- [Marketplace transfer routes](#marketplace-transfer-routes-apistorage)
- [Flows](#flows)
- [Collections](#collections)
- [Gotchas](#gotchas)

## Project render storage

### GET /api/collections/project_storage/records

- **Auth**: user token for a member of the organization that owns the linked
  project.
- **Purpose**: the only way to obtain per-project bucket credentials.
- **Typical query**: `?filter=(project_id='<projectRecordId>')&perPage=1&skipTotal=1`.

| Query param | Type | Required | Notes |
| --- | --- | --- | --- |
| `filter` | string | in practice yes | Use the exact project filter `(project_id='<id>')`. |
| `force_renew` / `renew` | `1`\|`true`\|`yes` | no | Forces immediate credential reissue with a fresh 7-day TTL. |
| `perPage`, `skipTotal`, `sort` | standard Sulu | no | `&sort=-updated&perPage=1&skipTotal=1` is what the Blender add-on sends. |

**Record fields**

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Record id. |
| `project_id` | relation → `projects` | Owning project. |
| `bucket_name` | string | Project storage bucket. |
| `access_key_id` | string | **Live credential.** |
| `secret_access_key` | string | **Live credential.** |
| `session_token` | string | **Live credential** (STS-style session token; required alongside the pair). |
| `expiry` | date | Credential expiry. Measured conservatively (from before the issuing call), so treat it as an early estimate. |
| `created`, `updated` | autodate | |

Credential scope: `object-read-write` over the **entire** bucket, 7-day TTL. That includes DELETE.

- **Side effects on read** (these are real, a GET here is not inert):
  - *Auto-renew*: on view or list, credentials that are incomplete or near
    expiry can be replaced with a fresh set.
  - *Auto-provision* (list requests only): if the result is empty, the filter names a `project_id`,
    and the caller is authorized for the project, the service may provision
    storage, issue credentials, save the row, and return it.
- **Errors**: 401 unauthenticated; 403 not a member of the owning organization; 500
  when credential renewal or storage provisioning fails.

### GET /api/collections/project_storage/records/{id}

Same auth rule and same auto-renew behavior as the list route; no auto-provision (that path is
list-only). Use the filtered list instead unless you already hold the record id.

### Client-side S3 usage (no Sulu endpoint)

| Setting | Value |
| --- | --- |
| Endpoint | The S3-compatible endpoint supplied for the Sulu environment |
| Region | `auto` |
| Bucket | `bucket_name` from the record |
| Auth | `access_key_id`, `secret_access_key`, `session_token` |

Use the endpoint configured by the trusted Sulu client environment.

Before reading credentials into an S3 client, bind the endpoint to a trusted
HTTPS origin. Reject userinfo, unexpected ports, paths, queries, fragments,
redirects, and arbitrary overrides.

Multipart uploads are allowed through the S3 protocol, unlike the marketplace
single-PUT routes.

---

## Render bucket key layout

Keys must match the documented layout or tasks fail during input retrieval.
`job_id` below is `job_data.id`; when `input_job_id` differs from `id` (duplicate jobs)
the **source** keys use `input_job_id` and only output uses `id`.

### Sources, project mode (`job_data` field `zip: false`)

| Object | Key |
| --- | --- |
| Main blend | `<bucket>/<project_path>/<main_file>` |
| Each dependency | `<bucket>/<project_path>/<path relative to project root>` |
| Manifest | `<bucket>/<project_path>/<input_job_id>.txt` |

The node uses the manifest to select inputs under the project prefix. The
manifest is plain text, one relative path per line, and must list the
dependencies plus the main scene. `main_file` is relative to `<project_path>`,
uses forward slashes, and is NFC-normalized.

### Sources, archive mode (`job_data` field `zip: true`)

| Object | Key |
| --- | --- |
| Archive | `<bucket>/<input_job_id>.zip` |

The node downloads and extracts the archive. Entries must not start
with `/` and must not contain `..`: that extractor silently strips those components rather than
rejecting the entry, so the file lands at an unintended path. `main_file` is relative to the archive
root.

### Add-ons (either mode, optional)

| Object | Key |
| --- | --- |
| Each packed add-on zip | `<bucket>/<input_job_id>/addons/<name>.zip` |

Names go in `job_data.packed_addons`. The node extracts them into a per-job Blender user path and
deletes the archives locally.

### Output (written by the render nodes)

| Object | Key |
| --- | --- |
| Composite frames | `<bucket>/<job_id>/output/composite/<frame>.<ext>` |
| Per-view-layer frames | `<bucket>/<job_id>/output/<layer>/<frame>.<ext>` |
| Thumbnails | `<bucket>/<job_id>/output/thumbnails/<frame>_<layer>.webp` |

Thumbnails are written by the thumbnail service (`sts.superlumin.al`), not by the render node's own
upload: the frame number is zero-padded to four digits and there is no size suffix in the key. Sized
variants are resized on the fly by that service, so do not look for `_32`/`_256` keys in the bucket.

The upload operation copies the node's local `output/<job_id>/<task>/` tree to
`<bucket>/<job_id>/output/`, preserving relative paths, so the exact subfolders depend on the
scene's output nodes and view layers. List the prefix rather than assuming names.

**Retention: 7 days.** Every `render-*` bucket carries the lifecycle rule
`delete-render-objects-after-7-days` with an empty prefix: all objects are deleted and incomplete
multipart uploads are aborted at 7 days. Nothing is exempt.

---

## Marketplace transfer routes (`/api/storage`)

Every route in this group requires a valid auth token (`apis.RequireAuth()`), with per-endpoint
authorization on top. These mutate marketplace catalog state; drive them from
[../sulu-market-seller/SKILL.md](../sulu-market-seller/SKILL.md) (uploads) or
[../sulu-market/SKILL.md](../sulu-market/SKILL.md) (buyer downloads), not from project work.

Presign TTLs: uploads **15 minutes**, downloads **2 minutes**. All uploads are a **single PUT**, no
multipart. Returned `headers` are part of the signature and must be sent verbatim.

### GET /api/storage/health

- **Auth**: any authenticated user. Operator probe, not part of normal client flows.
- **Response 200**: `{ok, timestamp, media: {configured, ready, corsReady, bucket, publicUrl, error?, corsError?}, files: {configured, ready, corsReady, bucket, error?, corsError?}}`.
- **Side effects**: none.

### POST /api/storage/media/upload/init

Start an image upload into the **public** media bucket.

- **Auth**: caller must own the product's `seller_org`, be an active member with a seller role
  carrying `content_write`, or be a platform admin. The seller org must be active. Finance and
  support-only roles are rejected.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `productId` | string | yes | |
| `kind` | string | yes | `avatar`, `gallery-pending`, `description`, or `wiki`. |
| `filename` | string | no | Decoded and then ignored: media keys are derived from `kind`, never from the filename. |
| `contentType` | string | yes | `image/png`, `image/jpeg`, or `image/webp`. |
| `contentLength` | int64 | yes | Bytes, minimum 1. |

Size caps by kind: avatar 2 MB, gallery-pending 10 MB, description 5 MB, wiki 5 MB.

The server derives deterministic keys from the declared media purpose and returns them to
the client. Use returned keys rather than constructing object names.

- **Response 200**: `{uploadUrl, uploadIntent, objectKey, publicUrl, headers: {"Content-Type", "Cache-Control"}, slot?}`.
  `uploadIntent` is an encrypted server-signed token binding actor, product, kind, key, content
  type, size and expiry; echo it to `complete`. `Cache-Control` is fixed to
  `public, max-age=31536000, immutable` and must be sent on the PUT.
- **Errors**: 400 invalid kind/MIME/size, 403 ownership, 503 unconfigured.
- **Side effects**: none yet (the intent token is stateless).

### POST /api/storage/media/upload/complete

- **Auth**: authorization is re-derived from `uploadIntent` (must belong to the caller, be
  unexpired, and re-pass the product ownership check), then the object is HEADed.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `uploadIntent` | string | yes | From init. |
| `productId`, `kind`, `objectKey`, `slot` | mixed | no | Legacy echo fields. If sent they must match the signed intent exactly, else 400. |

- **Validation**: HEAD size must be ≤ the signed max and ≤ the declared `contentLength`, and HEAD
  content type must equal the signed content type. A size violation **deletes the uploaded object**
  and returns 400; a content-type mismatch returns 400 but leaves the object in place.
- **Response 200**: `{ok: true, updated: "<product updated timestamp>"}`.
- **Side effects**: `description`/`wiki` bump `description_image_count`/`wiki_image_count`; `avatar`
  re-saves the product to bust caches; `gallery-pending` is a no-op until finalize.

### POST /api/storage/media/finalize-gallery

Atomically reorder, add and remove a product's gallery images into the product's ordered
gallery slots.

- **Auth**: product owner / `content_write` / platform admin.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `productId` | string | yes | |
| `items[]` | array | yes | Max 100. Array order is the final order. |
| `items[].source` | `existing`\|`pending` | yes | |
| `items[].slot` | int | for `existing` | Current slot number. |
| `items[].key` | string | for `pending` | Full object storage key, must start with `products/{id}/gallery/.pending/`. |

- **Response 200**: `{ok: true, gallery_count, updated}`. The returned `gallery_count` is the
  legacy-slot count only; the product stores `legacy_gallery_count = N` and
  `gallery_count = N + count(non-failed market_product_media gallery rows)`.
- **Side effects**: server-side copies via a `.tmp/` staging prefix, then deletion of surplus slots,
  the `.tmp/` keys, and **all** remaining `.pending/` objects. Send the complete final ordering:
  anything pending and unreferenced is destroyed.

### POST /api/storage/files/upload/init

Start a product-file (paid deliverable) upload into the **private** files bucket.

- **Auth**: product owner / `content_write` / platform admin.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `productId` | string | yes | |
| `filename` | string | yes | Sanitized for the key: spaces become hyphens, path components stripped. |
| `contentType` | string | yes | Archive allow-list: `application/zip`, `application/x-zip-compressed`, `application/x-rar-compressed`, `application/vnd.rar`, `application/x-7z-compressed`, `application/gzip`, `application/x-tar`, `application/x-blender`, `application/octet-stream`. |
| `contentLength` | int64 | yes | 1 byte to 5 GB. Products with `delivery_kind = "blender_asset"` cap at 4 GB. |

Delivery-kind rules: `blender_extension` must be a `.zip` with a zip-ish content type
(`application/zip`, `application/x-zip-compressed`, `application/octet-stream`); `blender_asset`
filenames must be `.blend` or an asset-library `.zip` with the exact descriptor content type.

- **Object key**: `products/{productId}/files/{uuid}/{sanitized-filename}`.
- **Response 200**: `{uploadUrl, objectKey, assetId, maxBytes, headers}`. `headers` includes
  `If-None-Match: *` (write-once: the URL cannot overwrite an existing object) and `Content-Type`.
- **Side effects**: creates a `product_files` row with `asset_status: "pending"`.

### POST /api/storage/files/upload/complete

- **Auth**: product owner / `content_write` on the product behind the `product_files` record.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `assetId` | string | yes | The `product_files` id from init. |

- **Validation**: `HeadObject` (with one 1 s retry for object storage consistency); actual size must pass the
  product's size validator and be ≤ the declared `file_size`; content type must match the recorded
  `upload_content_type` (or the descriptor type for blender assets with none recorded). Either
  violation **deletes the object storage object** and returns 400, so restart from init.
- **Response 200**: `{ok: true}`.
- **Side effects**: sets `asset_status: "ready"` and `file_size` to the actual byte count.

### POST /api/storage/files/download/init

One endpoint, two modes selected by the presence of `entitlementId`.

**Buyer mode** (`entitlementId` present):

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `entitlementId` | string | yes | Must be `status: "active"` and resolve to the caller. |
| `fileId` | string | yes | A `product_files` id belonging to the entitled product. |

- **Auth**: the entitlement's canonical subject must resolve to the caller. Org-grant entitlements
  follow **current** org membership: the historical purchaser loses access after leaving the org.
- **Checks**: the file must be `asset_status: "ready"` and pass manual buyer-file delivery
  resolution (it must be an artifact of a published catalog revision the entitlement tier allows).
  The delivered key comes from the resolved catalog artifact, not the raw record.
- **Response 200**: `{download: {url, expiresAt, filename}}`. Presigned GET, `Content-Disposition:
  attachment`, TTL 2 minutes.
- **Side effects**: increments `products.total_downloads`, inserts a `downloads` audit row
  (entitlement, product file, product version, user, hashed IP, user agent), and stamps
  `entitlement.last_downloaded_version`. **Not a read-only call. Never poll or retry it in a loop.**

**Seller self-download mode** (`entitlementId` omitted or empty): send only `fileId`. Requires
`content_write` on the product's `seller_org`. Same response shape, no counters, no audit row, no
entitlement stamp. Returns 409 when the product's Blender-extension identity is retired.

- **Errors (both modes)**: 400 missing or not-ready file, or missing `object_key` ("use legacy
  download"); 403 entitlement or ownership failure; 404 unknown ids. An empty `entitlementId` flips
  the mode, so a buyer who omits it gets a seller-gate 403 rather than a useful error.

### Product-media routes

Modern product media uses the authenticated routes documented by
[sulu-market-seller](../sulu-market-seller/SKILL.md). Follow that skill for
payloads, ordering, pruning, updates, and deletion.

---

## Flows

### Project storage: credentials, upload, download

1. Authenticate as a member of the project's organization
   ([../sulu-api/SKILL.md](../sulu-api/SKILL.md)).
2. `GET /api/collections/project_storage/records?filter=(project_id='<projectId>')&perPage=1&skipTotal=1`.
   Existing storage comes back with credentials already renewed to at least 1 hour of validity;
   missing storage is provisioned during this call.
3. Take `bucket_name`, `access_key_id`, `secret_access_key`, `session_token` into environment
   variables. Do not print or persist them.
4. Transfer with any S3 client against the object storage endpoint. Uploads may be multipart.
5. For long transfers, re-fetch the record with `&force_renew=1` before starting to guarantee a
   fresh 7-day set.

### Render submission upload (PROJECT mode)

1. Fetch credentials as above.
2. `copyto` the main blend to `:s3:<bucket>/<project_path>/<main_file>`.
3. `copy --files-from <deps-list>` the dependencies to `:s3:<bucket>/<project_path>/`.
4. Upload the manifest (dependencies + main blend, one relative path per line) to
   `:s3:<bucket>/<project_path>/<job_id>.txt`.
5. Optional: upload packed add-on zips to `:s3:<bucket>/<job_id>/addons/`.
6. Only then submit the job with matching `project_path`, `main_file`, `zip: false`, `id`, and
   `packed_addons`. See [../sulu-render/SKILL.md](../sulu-render/SKILL.md).

### Render submission upload (ZIP mode)

1. Pack the blend and its dependencies into `<job_id>.zip` (no leading `/`, no `..` in entry names).
2. Upload to `:s3:<bucket>/<job_id>.zip`.
3. Optional add-ons to `:s3:<bucket>/<job_id>/addons/`.
4. Submit with `zip: true` and `main_file` relative to the archive root.

### Downloading render output

1. Fetch credentials.
2. List `<bucket>/<job_id>/output/` to see what exists.
3. Sync or get the keys you want, within 7 days of the render finishing.
4. Alternative without holding credentials: `GET /api/jobs/{org_id}/{job_id}/source_manifest` and
   `POST /api/jobs/{org_id}/{job_id}/source_urls` return presigned frame URLs (both require an auth
   token and job access). Documented in [../sulu-render/SKILL.md](../sulu-render/SKILL.md).

### Marketplace product-file upload

1. `POST /api/storage/files/upload/init` → keep `assetId`, `uploadUrl`, `headers`.
2. `PUT <uploadUrl>` with the bytes and exactly those headers, within 15 minutes, single request.
   A retry after a successful PUT fails with 412 (write-once); re-run init for a new key.
3. `POST /api/storage/files/upload/complete` with `{assetId}`.

### Marketplace media upload

1. `POST /api/storage/media/upload/init` → `uploadUrl`, `uploadIntent`, `headers`.
2. `PUT <uploadUrl>` with the image bytes and the returned `Content-Type` and `Cache-Control`.
3. `POST /api/storage/media/upload/complete` with `{uploadIntent}`.
4. Gallery only: upload each new image as `gallery-pending`, then
   `POST /api/storage/media/finalize-gallery` with the complete final ordering.

### Buyer download

1. Get `entitlementId` (from `entitlements`) and `fileId` (a `product_files` id).
2. `POST /api/storage/files/download/init` with both.
3. `GET download.url` within 2 minutes. One init per real download: it moves public counters.

---

## Collections

### `project_storage`

Fields are listed above. Organization members may read the record. User-facing
writes are unavailable. Deleting the project deletes its associated storage.

### `projects`, storage-relevant behavior

Project creation provisions storage and temporary credentials. Project deletion
deletes associated storage and rendered outputs.

### `product_files`

`product`, `object_key`, `upload_content_type`, `asset_status` (`pending` → `ready`),
`distribution_kind`, `archive_hash`, `archive_size`, `file_size`, `name`, `product_version`.
Direct record reads are unavailable to a user token. Use the documented
`/api/storage` routes.

### Touched by `files/download/init`

`entitlements` (must be active; `last_downloaded_version` stamped), `downloads` (audit rows),
`products` (`total_downloads`, `description_image_count`, `wiki_image_count`, `gallery_count`,
`legacy_gallery_count`, `seller_org`, `delivery_kind`, `extension_id`).

---

## Gotchas

- **A `project_storage` list read has side effects**: it can renew credentials
  and provision storage. Do not use it as a cheap existence check.
- **Credentials are bucket-wide read/write/delete.** Nothing stops an S3 client from deleting the
  user's frames. Treat delete as a destructive action needing explicit approval.
- **`expiry` is conservative** (stamped before the issuing call). Re-read the record rather than
  persisting credentials; add `force_renew=1` before a long transfer.
- **7-day bucket lifecycle, no exceptions.** Objects are deleted and incomplete multipart uploads
  aborted at 7 days, across the whole bucket.
- **Bucket names are service-assigned.** Always read `bucket_name`; never
  derive it.
- **Layout must match the mode flags.** `zip: true` expects `<job_id>.zip` at the bucket root;
  `zip: false` expects loose files plus the manifest under `<project_path>/`. A mismatch fails the
  download operation on every task.
- **Upload before registering the job.** Nodes start downloading as soon as the job is queued.
- **Presigned headers are signed.** Send exactly what init returned. Product-file PUTs are
  write-once (`If-None-Match: *`): a repeat PUT gets 412.
- **No multipart on `/api/storage`.** One PUT, up to 5 GB (4 GB for `blender_asset` sources).
  Project render buckets accept multipart because clients hold real credentials.
- **Content type is enforced end to end** for marketplace uploads: declared at init, signed into the
  URL, re-verified by HEAD at complete. On the product-file path a mismatch deletes the uploaded
  object; on the media path it only returns 400.
- **Match errors on the `error` field** of `/api/storage` responses (`message` is identical) and
  keep `traceId` for support.

Output subfolder names beyond `composite` and `thumbnails` depend on the scene's
view layers and output nodes. List the prefix instead of assuming.
