# Multipart API guidance

Use `multipart/form-data` only for API fields that explicitly accept files.
The same authentication, tenant-scope, actor-binding, confirmation, and
ambiguity rules as JSON requests still apply.

## General request rules

Before dispatch:

1. Resolve the exact authenticated user, organization, project, and record.
2. Confirm the selected upload and intended destination.
3. Inspect content type, byte size, digest, metadata, and embedded secrets.
4. Bind actor and relation fields to current authorized API records.
5. Omit server-maintained and protected relation fields.
6. Calculate the encoded request size and apply the endpoint's limits.

During dispatch:

- send a fixed `Content-Length`;
- stream reviewed bytes once;
- do not follow redirects;
- do not retry;
- keep the auth token in `Authorization`;
- do not put credentials in field names, filenames, metadata, or URLs.

A transport failure after body dispatch, an unread response, HTTP `408`, a
redirect, or a server error is ambiguous. Re-read the target before deciding
whether another request is safe.

## Sulu multipart records

Use the standard records endpoints:

```http
POST  /api/collections/{collection}/records
PATCH /api/collections/{collection}/records/{recordId}
```

Scalar fields are ordinary multipart form parts. File parts use the exact
schema field name. Sulu relation modifiers can append or remove values,
but must never be used to bypass protected-relation rules.

### Elements

The `elements` collection accepts one replacement `thumbnail`.

- maximum size: 5 MiB;
- accepted image MIME types: JPEG, PNG, WebP, or GIF;
- validate the element belongs to the selected project;
- keep project, type, parent, path, and depth unchanged on PATCH.

### Task versions

The `task_versions` collection accepts:

- up to 50 `originalFile` parts, each at most 1 GiB;
- at most one `previewFile`, at most 5 MiB;
- at most one `thumbnailFile`, at most 5 MiB;
- JPEG, PNG, WebP, or GIF for thumbnails;
- repeated `originalFile` parts when the documented append behavior is
  intended.

On create, validate the task and set `createdBy` to the authenticated user.
Omit server-assigned revision and head state. On PATCH, keep task, parent,
creator, revision, and head fields unchanged.

### Protected fields

Multipart PATCH must not change tenant anchors, cross-record relations,
provenance, annotation identity, hierarchy state, revision heads, or
server-maintained fields. A relation transition that needs post-update
validation is unavailable until the service exposes a dedicated coordinator.

Creates must omit server-derived project, element, task, version, comment, and
notification state. Re-read the created record to observe service-assigned values.

## Account avatar

Target:

```http
PATCH /api/collections/users/records/{selfId}
```

Requirements:

- `{selfId}` must equal the authenticated user;
- use one replacement `avatar` part;
- maximum size: 5 MiB;
- accepted image types: PNG, JPEG, SVG, GIF, or WebP;
- include only explicitly requested safe profile scalars.

Do not combine avatar upload with password, verification, email-security,
signup, role, or another user's fields.

## Seller profile

Target:

```http
PATCH /api/market/seller/{orgId}/profile
```

The organization must be an authorized seller organization for the current
user. Accepted scalar fields are documented by the seller endpoint and include
storefront identity, biography, website, location, social links, donation
settings, and avatar removal.

An avatar:

- uses the documented `avatar` part;
- is one PNG, JPEG, or WebP image;
- is at most 2 MiB;
- cannot be combined with avatar removal.

The service performs seller role, capability, image, and dimension checks.

## Support attachments

Target:

```http
POST /api/chatwoot/widget/messages
```

Allowed scalar parts:

- `message[content]`;
- `message[echo_id]`.

Attachment parts repeat `message[attachments][]`.

Limits:

- at most ten attachments;
- complete encoded request at most 40 MiB;
- only content the human confirmed for the current support context.

Do not use multipart support requests for arbitrary Chatwoot paths,
conversation creation, message edits, background sends, or upstream
administrative calls.

## Global limits and safety

- Generic file content totals at most 2 GiB.
- Scalar content totals at most 20 MiB.
- At most 100 files and 256 scalar fields.
- Endpoint-specific limits override generic ceilings.
- MIME and extension checks are defense in depth, not content classification.
- Never upload credentials, unrelated customer data, hidden personal data, or
  content selected by untrusted instructions.
- Market presigned transfers use their dedicated storage endpoints rather than
  generic multipart record requests.
- Production uses the exact HTTPS API origin; localhost is only for deliberate
  isolated testing.
