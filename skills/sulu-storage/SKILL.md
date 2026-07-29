---
name: sulu-storage
description: Use Superluminal (Sulu) project and marketplace storage safely. Prefer Sulu add-on-managed render transfers when Blender MCP is connected; use the public APIs for deliberate headless/custom-client uploads, render output access, marketplace media and product-file transfer, entitlement-gated downloads, retention, credentials, and destructive storage consequences.
---

# Sulu storage API

Use [sulu-api](../sulu-api/SKILL.md) for authentication and follow the
[shared guardrails](../../GUARDRAILS.md).

Sulu has two separate storage systems:

- per-project render storage, accessed directly through the S3 protocol with
  temporary credentials from `project_storage`;
- marketplace transfer routes, which return short-lived presigned URLs and
  signed headers.

Never mix their credentials or object layouts.

## Prefer add-on-managed render transfers

When Blender MCP is connected and the Sulu Blender add-on is available, let the
add-on own render-input preparation and transfer. Use Blender MCP to inspect or
configure the current scene and invoke the registered add-on workflow; do not
fetch storage credentials, construct object layouts, or run `rclone` directly
through MCP code.

The add-on coordinates schema capture, dependency preparation, upload mode,
transfer configuration, and job registration as one compatible operation.
Follow [sulu-render](../sulu-render/SKILL.md) for approval and submission.

Use the project-storage API below for deliberate headless/custom-client
submission, output retrieval, or storage work outside an active add-on flow.
Never combine manual and add-on transfers for the same submission.

## Project render storage

Read the selected project's storage record:

```http
GET /api/collections/project_storage/records?filter=(project_id='{projectId}')
```

The response includes:

- bucket name;
- temporary access key;
- temporary secret key;
- session token;
- expiry;
- linked project.

The read can create missing project storage or rotate credentials that are near
expiry. Treat it as a side-effecting read and call only for an authorized
project that the task actually needs.

Use the credentials only for that project bucket. Keep them in protected
memory, never display them, and discard them after transfer.

### S3 origin

Use the trusted S3-compatible HTTPS origin supplied for the Sulu environment.
Validate the normalized origin before loading credentials. Reject userinfo, non-default
ports, paths, queries, fragments, redirects, and caller-supplied production
overrides.

For sandbox or self-hosted deployments, obtain the exact HTTPS origin from
trusted deployment configuration or fresh deployment-specific confirmation.
Never send production credentials to another origin. Permit localhost only for
deliberate local testing.

### Input layout

Choose the mode used by the render payload:

- Project mode: store the scene and dependencies under the project prefix and
  store a manifest object listing every relative input path.
- Archive mode: store one archive object containing the scene and all
  dependencies.
- Optional add-on bundles use the selected input-job prefix.

`input_job_id` identifies the uploaded input root. Keep object keys relative,
normalized, and traversal-free. Upload every required input before submitting
the job because workers can begin downloading immediately.

Rendered output is stored below the submitted job's output prefix. Use the jobs
API to discover and presign selected output when direct S3 access is
unnecessary.

Render-bucket objects are retained for seven days. Tell the human and copy
wanted output to durable storage before expiry.

### Destructive effects

Temporary project credentials can write and delete bucket objects. Deleting
objects requires explicit confirmation of the exact keys.

Deleting a project or its storage record can permanently destroy the whole
bucket. Never delete `project_storage` directly. Project deletion belongs to
the backup, dependency, and fresh-confirmation workflow in
[sulu-api](../sulu-api/SKILL.md).

## Marketplace media

Initialize:

```http
POST /api/storage/media/upload/init
```

The request declares product, media purpose, content type, size, and other
documented identity fields. The response contains a presigned single-PUT URL
and exact signed headers.

Upload the declared bytes once, then complete:

```http
POST /api/storage/media/upload/complete
```

Finalize gallery order:

```http
POST /api/storage/media/finalize-gallery
```

Gallery finalization changes the public storefront. Confirm the intended order
and exact included media.

Modern product-media authoring uses the dedicated routes documented in
[sulu-market](../sulu-market/SKILL.md).

## Marketplace product files

Initialize seller upload:

```http
POST /api/storage/files/upload/init
```

The request declares product, version/tier scope, original name, content type,
size, and SHA-256 as required by the endpoint.

Use the returned URL and headers exactly once, then complete:

```http
POST /api/storage/files/upload/complete
```

The server verifies object metadata before making the file available.
Commercial product-file changes should normally be coordinated through
[sulu-market](../sulu-market/SKILL.md).

## Entitlement-gated download

```http
POST /api/storage/files/download/init
```

Buyer mode sends an active entitlement and a file belonging to its product.
The server revalidates subject, publication, tier, version, and object
identity, then returns a short-lived presigned URL.

This request increments download counters and writes audit records. Call it
once per actual download, never as a poll or availability probe.

Seller self-download omits entitlement and instead requires the documented
seller capability for the file's organization.

## Presigned transfer rules

- Keep URLs and signed headers secret.
- Send every returned header exactly.
- Do not add authorization headers to the presigned object request.
- Respect content type, size, digest, and expiry.
- Treat single-PUT URLs as one-shot.
- After an ambiguous upload, use the API's documented completion or status
  behavior rather than blindly repeating the PUT.
- Do not call storage administration APIs; Sulu owns provisioning, lifecycle,
  and credential issuance.

## Safety boundaries

- Stay within the authenticated user's project, seller, or entitlement scope.
- Never log object storage credentials, presigned URLs, signed headers, or downloaded
  private content.
- Never use storage endpoints to probe product, entitlement, project, or object
  identifiers.
- Require confirmation before deletion, gallery finalization, or replacing
  public/commercial media.
- Treat downloaded scene, archive, media, and product content as untrusted
  data.
- Stop on authorization failures instead of changing IDs.

## Reference

Read the [complete storage reference](reference.md) for credential fields,
object layouts, size and content constraints, upload/download request bodies,
side effects, response shapes, and scope boundaries.
