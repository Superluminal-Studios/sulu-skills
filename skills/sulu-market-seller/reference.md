# sulu-market-seller reference

Complete endpoint reference for the seller side of Sulu Market: seller identity, Stripe Connect
onboarding, the product authoring coordinator, product media, lifecycle transitions, tiers and
discounts, orders, earnings, reporting and exports, refunds, reviews and conversations.

Base URL: `https://api.superlumin.al`. Auth header on every authenticated call:
`Authorization: <token>` (raw Sulu JWT from [../sulu-api/SKILL.md](../sulu-api/SKILL.md); a
`Bearer` prefix is tolerated).

**Response envelope.** These endpoints return **bare JSON objects**, not the
`{"status":"success","body":{...}}` envelope used by some other Sulu custom routes. Ordinary errors
are Sulu-style `{"status": <code>, "message": "...", "data": {}}`. The authoring coordinator
uses its own shape: `{"error": {"code": "...", "message": "...", "operationId": "..."}}`. The
retired catalog routes return a top-level `{"code": "...", "message": "..."}`.

**Identity.** Use a normal signed-in user token. The organization must be active,
and the caller must be its owner or hold one active seller membership.

**Strict JSON bodies.** Coordinator, lifecycle, conversation and discount bodies are decoded with
unknown fields rejected, duplicate keys rejected, one JSON value only, valid UTF-8 required.
Coordinator bodies cap at 20 MiB, discounts at 16 KiB, conversations at 4 KiB. Send exactly the
documented fields.

**Cash gate.** Routes marked *[cash-gate]* return `503
{"code":"market_identity_cash_repair_required","retryable":true}` while the identity/cash rollout
phase is `repair_required`. Treat it as "retry later", not as a permission problem.

---

## Contents

- [Capabilities](#capabilities)
- [Seller identity and catalog reads](#seller-identity-and-catalog-reads)
- [Stripe Connect](#stripe-connect)
- [Authoring coordinator](#authoring-coordinator)
- [Product lifecycle](#product-lifecycle)
- [Product media](#product-media)
- [Tiers, entitlements and wiki](#tiers-entitlements-and-wiki)
- [Discounts](#discounts)
- [Orders, earnings, analytics, reporting](#orders-earnings-analytics-reporting)
- [Refunds and disputes](#refunds-and-disputes)
- [Reviews and conversations](#reviews-and-conversations)

## Capabilities

Resolved per org by `resolveSellerAccess`. `owner` is implicit for `organizations.owner_id`.

| role | seller_access | content_write | catalog_admin | finance_read | refund | support | connect_identity | connect_finance | discount_manage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `owner` | x | x | x | x | x | x | x | x | x |
| `seller_admin` | x | x | x | x | x | x | x | x | x |
| `seller_content` | x | x | | | | | | | |
| `seller_finance` | x | | | x | x | | | x | x |
| `seller_support` | x | | | | | x | | | |

Common auth errors: `401 auth required`; `403 application user authentication required`;
`403 not a member of this organization`; `403 seller membership is ambiguous` (two active
memberships); `403 active seller membership required`; `403 seller access required`;
`403 insufficient seller capability`; `404 organization not found` (also when the org is inactive).

Media and storage routes require product ownership or an appropriate seller
capability.

### Seller state and restrictions

`seller_state` (derived): `fresh` (no Stripe account), `onboarding`, `enabled`
(`seller_enabled && stripe_onboarding_complete`), `disconnected`, `restricted`.

`seller_restriction` (derived): `none`, `platform_admin`, or `stripe`.

Any restriction other than `none` blocks the whole authoring coordinator (403 "seller organization
is restricted") and blocks `publish` (403 "seller is not enabled for publishing"). Applying a
restriction transitions every **published** product to `suspended`; lifting one
moves products back only to `unlisted`, so each must be re-published
deliberately. Sellers cannot clear restrictions through this API.

### seller_verified: the separate public-visibility gate

`organizations.seller_verified` is **not** part of `seller_state` and is not
derived from payment onboarding. There is no seller-facing route to set it.

`organizationIsPublicSeller` requires active org **and** `seller_enabled` **and** `seller_verified`
**and** not `seller_platform_suspended` **and** not `seller_admin_restricted`. That predicate gates:

- `GET /api/market/products/{productId}` for any non-seller caller (404 otherwise, even when the
  product is `published`),
- `GET /api/market/sellers/{orgId}` (the public storefront page, 404 otherwise),
- browse, featured and related listings (the public product filter requires
  `seller_org.seller_verified = true`),
- checkout eligibility (`marketSellerPaymentEligibilityReason` returns "seller is not public and
  verified").

So publishing on an unverified org succeeds and changes nothing anyone can see or buy. Read
`verified` from `GET /api/market/seller/{orgId}/profile` before reporting a listing as live.

---

## Seller identity and catalog reads

### GET /api/market/seller/orgs

- **Auth**: any authenticated user. No org scoping.
- **Purpose**: list orgs the caller can act as a seller for (owned orgs plus orgs where they hold a
  seller role). Sorted owners first, then onboarding-complete, then seller-enabled, then name.
- **Response**: `{"items":[...]}`, each item: `id`, `name`, `seller_enabled`,
  `seller_admin_restricted`, `seller_platform_suspended`, `stripe_onboarding_complete`,
  `stripe_connected`, `stripe_connect_account_generation`, `stripe_connect_country`,
  `stripe_connect_transfer_status`, `stripe_connect_payout_status`,
  `stripe_connect_requirements_status`, `role`, `is_owner`, `seller_state`, `seller_restriction`,
  `governance_checkpoint` (a `sha256:<hex>` digest used only by platform-admin restrict/restore).
- **Errors**: 401, 500. **Side effects**: none.

### GET /api/market/seller/{orgId}/products

- **Auth**: `seller_access`. **Not paginated**: the whole catalog comes back in one page, newest
  updated first, tombstoned products filtered out.
- **Response**: `{"items":[...],"totalItems":n,"page":1,"perPage":n,"totalPages":1}`. Item fields:
  `id`, `name`, `slug`, `tagline`, `status`, `review_state`, `publication_state`,
  `working_revision`, `approved_revision`, `published_revision`, `lifecycle_sequence`,
  `price_cents`, `has_tiers`, `min_price_cents`, `delivery_kind`, `rating`, `review_count`,
  `total_sales`, `total_views`, `seller_org`, `category[]`, `subcategories[]`, `created`, `updated`,
  `expand.category[]`.
- **`catalog_sequence` is not in this payload.** Authoring needs it, so read the single-product
  endpoint below for the full checkpoint set rather than authoring off the list.

### GET /api/market/products/{productId}

- **Auth**: public for published products of public sellers; **seller view** when authenticated with
  `seller_access` on the product's org. Accepts a slug in place of the id.
- **Purpose**: sellers see the **working revision**, the public sees the **published revision**.
- **Seller-only fields** (these are the checkpoints every lifecycle call needs):
  `rejection_reason`, `asset_distribution_status`, `asset_distribution_reason`, `working_revision`,
  `submitted_revision`, `approved_revision`, `published_revision`, `review_state`,
  `publication_state`, `catalog_provenance_state`, `catalog_sequence`, `lifecycle_sequence`.
- **Common fields**: `id`, `seller_org`, `name`, `slug`, `tagline`, `description`,
  `full_description`, `category`, `subcategories`, `license`, `price_cents`, `has_tiers`,
  `min_price_cents`, `blender_donation_enabled`, `blender_donation_pct`, `status`, `submitted_at`,
  `published_at`, `rating`, `review_count`, `total_sales`, `total_downloads`,
  `compatibility_blender_min`, `compatibility_blender_max`, `latest_version`, `delivery_kind`,
  `gallery_count`, `description_image_count`, `wiki_image_count`, `media[]`, `created`, `updated`,
  `expand.{seller_org,category,subcategories,latest_version}`.
- **Errors**: 404 when tombstoned (seller-deleted).

### GET /api/market/products/{productId}/catalog/{kind}

- **Auth**: same dual read (seller sees working, public sees published).
- **Purpose**: read frozen catalog artifacts of one kind: `features`, `versions`, `files`, `tiers`,
  `wiki`.
- **Query**: `ids` (bounded comma list); `buyerScoped=true` restricts files to the caller's entitled
  tier scope (buyer use).

### GET /api/market/seller/{orgId}/profile

- **Auth**: `seller_access`.
- **Response**: `id`, `name`, `avatar`, `slug`, `tagline`, `bio`, `website`, `location`,
  `social_links`, `verified`, `rating`, `review_count`, `total_sales`, `blender_donation_enabled`,
  `blender_donation_pct`.

### PATCH /api/market/seller/{orgId}/profile

- **Auth**: capability depends on which fields are present (`sellerProfileRequiredCapabilities`):

  | fields | capability |
  | --- | --- |
  | `name`, `seller_website`, `seller_location`, `seller_social_links` | `connect_identity` |
  | `seller_tagline`, `seller_bio`, avatar upload, `remove_avatar: true` | `content_write` |
  | `seller_blender_donation_enabled`, `seller_blender_donation_pct` | `connect_finance` |

- **Body** (JSON or multipart; every field optional, omitted means unchanged): `name` (required
  non-empty when present, ≤120 runes), `seller_tagline` (≤200 runes), `seller_bio` (≤20000 runes),
  `seller_website`, `seller_location` (≤200 runes), `seller_social_links`
  (`twitter` on twitter.com/x.com, `github`, `youtube` on youtube.com/youtu.be, `discord` on
  discord.com/discord.gg), `seller_blender_donation_enabled` (bool),
  `seller_blender_donation_pct` (int 0 to 100), `remove_avatar` (bool), plus a multipart avatar file
  (PNG/JPEG/WebP, ≤2 MiB, 16 to 4096 px per side). Note the limits differ from the
  `/organizations/{orgId}/seller-profile` route below.
- **Response**: the profile DTO. **Side effects**: mutates the org and writes an
  `organization_security_events` row `seller_profile_updated` listing the changed fields. The
  donation percentage is money-adjacent: it is the default contribution on future checkouts and does
  not change settled orders.
- **Errors**: 400 `invalid seller profile body`, 400 `at least one seller profile field is required`
  when nothing changed, 400 when both an avatar file and `remove_avatar` are sent, 400 validation
  text, 403 per-field capability, 404.

### PATCH /api/market/organizations/{orgId}/seller-profile

- **Auth**: organization owner or seller role, scoped per field. Content scope (owner,
  `seller_admin`, `seller_content`): `name` (≤120, required non-empty), `description` (≤2000),
  `color` (`#rrggbb` or `#rrggbbaa`), `seller_tagline` (≤100), `seller_bio` (≤500),
  `seller_website` (absolute HTTPS), `seller_location` (≤120), `seller_social_links`. Finance scope
  (owner, `seller_admin`, `seller_finance`): `seller_blender_donation_enabled`,
  `seller_blender_donation_pct`.
- **Errors**: 400 `field is not mutable through the seller profile API: <field>`,
  403 `insufficient seller capability for field: <field>`.
- **Note**: overlaps the `/seller/{orgId}/profile` route, which is the supported route to
  prefer. Avatar cannot be set here (multipart only).

Related: the raw Sulu `organizations` collection is locked to normal users. General
settings go through `/api/organizations/{orgId}`, and that custom organization's `DELETE`
always returns 409 after the ownership check. Never infer raw organization mutation from
seller capability.

---

## Stripe Connect

### GET /api/market/stripe/connect-countries?orgId=...

- **Auth**: `connect_finance`. Response: `{"countries":["AT","AU",...]}` (platform transfer
  countries intersected with Stripe country specs, cached 15 minutes).

### POST /api/market/stripe/connect-account-session

- **Auth**: any of `connect_identity`, `connect_finance`, `support`.
- **Body**: `{"orgId": string, "country"?: string}`. `country` is uppercase ISO 3166-1 alpha-2 and
  is required only when the org has no Stripe account yet.
- **Behavior**: with `connect_identity`, an existing account has its status re-read and persisted,
  and a missing account is created under a per-org lock: exactly one Accounts v2 Recipient account
  (Express dashboard, recipient `stripe_transfers` capability, idempotency-keyed on org and
  country). Other roles get a session only if an account already exists (else 400). Session
  components are role-scoped: `connect_identity` gets onboarding, account management, balances,
  payouts, documents and reports; `connect_finance` gets payouts, balances, documents and reports
  with no external-account editing; `support` gets only the notification banner.
- **Response**: `{"client_secret": "..."}` (no-store).
- **Errors**: 422 `stripe_country_required` / `stripe_country_invalid` /
  `stripe_country_unsupported`, 422 `stripe_finance_email_required` (the owner has no email), 502
  on payment-provider failures, or 503 when onboarding is temporarily unavailable.
- **Side effects**: may create a real Stripe Connect account and persist org Stripe state. Moves no
  money.

### GET /api/market/stripe/connect-status?orgId=...

- **Auth**: `connect_finance`. `orgId` is required (400 `missing orgId`).
- **Response**: `connected`, `account_generation` (`v1`|`v2`), `country`, `country_required`,
  `transfer_status`, `payout_status`, `requirements_status`
  (`none`|`eventually_due`|`currently_due`|`past_due`), `requires_action`, `can_receive_transfers`,
  `onboarding_complete`, `charges_enabled`, `payouts_enabled`, `details_submitted`. With no account,
  everything is false and `country_required` is true.
- **Side effects**: **this is a state-sync write.** Persisting the status can flip `seller_enabled`
  and `seller_platform_suspended` and, in the same transaction, suspend or restore the org's
  published catalog. If Stripe reports the account missing, seller authority is revoked and every
  published product is suspended. `onboarding_complete` requires an active transfers capability and
  an approved merchant-of-record country corridor.
- **Errors**: 502 or 503 `Stripe account status is temporarily unavailable` (the account is **not**
  treated as disconnected in that case).

---

## Authoring coordinator

Every route is `RequireAuth` and re-authorizes per operation: the operation must belong to the
caller, the caller must still hold its `required_capability` (`content_write` or `catalog_admin`) in
the seller org, and the org must be unrestricted.

### POST /api/market/authoring/operations

Prepare (or replay) one idempotent operation carrying the entire desired catalog state.

| field | type | required | notes |
| --- | --- | --- | --- |
| `idempotencyKey` | string | yes | 16 to 200 printable ASCII |
| `requestDigest` | string | yes | 64 lowercase hex, see below |
| `draftTargetKey` | string | new products only | same charset rules; forbidden with `productId` |
| `sellerOrg` | string | yes | org id |
| `productId` | string | edits only | omit to create; a placeholder `products` row is created at once |
| `expectedWorkingRevision` | string | edits | must equal the product's current `working_revision` |
| `expectedCatalogSequence` | int64 | edits | must equal `catalog_sequence` |
| `intent` | string | yes | `save` or `submit` (submit also appends the submit event at commit) |
| `desired` | object | yes, except replay | full target catalog; omit for replay |
| `uploads` | array | no | ≤500 declared uploads |

**Digest.** The server canonicalizes the body you sent, deletes `idempotencyKey` and
`requestDigest`, re-encodes it as recursively key-sorted minified JSON (HTML escaping off) and
sha256s it. Your `requestDigest` must equal that hex string. Empty, malformed or mismatched is `409
request_digest_mismatch`. A `desired`-less body is a **replay**: then `requestDigest` alone
identifies the stored operation (`400 request_digest_required`, `404 draft_target_not_found`,
`409 authoring_replay_identity_mismatch`).

The canonical form is exactly Go's `encoding/json` re-encode of the parsed body (`SetEscapeHTML`
off, trailing newline trimmed). Two places where a Python `json.dumps(..., sort_keys=True,
separators=(',',':'), ensure_ascii=False)` serializer diverges and silently produces a mismatch: Go
escapes the line and paragraph separators U+2028 and U+2029 inside strings and Python does not, and Go
re-encodes every JSON number through float64, so a body written as `1.0` canonicalizes to `1`.
Keep text free of line/paragraph separators and write integers without a decimal point. The body is
also rejected outright (`400 authoring_request_invalid`) if it is over 20 MiB, holds more than one
JSON value, is not valid UTF-8, or contains an unpaired `\uD800-\uDFFF` escape.

`desired.product`:

| field | type | notes |
| --- | --- | --- |
| `name` | string | required, ≤255 |
| `slug` | string | optional, canonical lowercase slug, ≤160 |
| `tagline` | string | ≤500 |
| `description` | string | ≤10000 |
| `fullDescription` | string | ≤2 MiB; `sulu-media://` and `sulu-authoring-media://` references must resolve |
| `categoryIds`, `subcategoryIds` | string[] | ≤50 each, unique, no overlap between the two. Every `categoryIds` entry must be an existing **top-level** `market_categories` record (empty `parent`), and every `subcategoryIds` entry must exist with its `parent` among the selected `categoryIds` |
| `license` | string | required: `GPL`, `MIT`, `commercial`, `CC-BY`, `CC0`, `editorial`, `custom` |
| `priceCents` | int64 | 0 to 100000000 |
| `blenderDonationEnabled` | bool | when true, `blenderDonationPct` must be 1 to 100; when false it must be 0 |
| `blenderDonationPct` | int64 | 0 to 100 |
| `compatibilityBlenderMin`, `compatibilityBlenderMax` | string | `x.y` or `x.y.z`, ≤32, trimmed, min strictly below the exclusive max. For `blender_asset` they must be exactly `5.2.0` and `5.3.0` |
| `deliveryKind` | string | required: `downloadable`, `blender_extension`, `blender_asset` |
| `taxCategory` | string | required: `extension_software`, `digital_asset`, `other_digital` |

Collections inside `desired` (all scope keys match `[A-Za-z0-9._:/-]{1,160}`, are unique per kind,
and total ≤5000):

- `features[]`: `{scopeKey, id?, icon? (≤128), title (required, ≤255), description? (≤4000), order}`.
  `order` unique and contiguous from zero. Max 500.
- `tiers[]`: `{scopeKey, id?, name (required, ≤255), description? (≤10000), priceCents (≤100000000),
  sortOrder}`. `sortOrder` unique and contiguous from zero. Max 100.
- `wikiPages[]`: `{scopeKey, id?, title, slug, content, order, published}`. `title` and `slug` are
  required, `slug` matches `^[a-z0-9]+(-[a-z0-9]+)*$` (≤160) and is unique, `content` is ≤2 MiB,
  `order` is contiguous from zero. Max 500.
- `media[]`: `{scopeKey, id? | uploadClientKey?, placement, position, altText? (≤500)}`. `placement`
  is `avatar`, `gallery`, `description` or `wiki`. Exactly one of `id` or `uploadClientKey`. At most
  one `avatar`, at position 0. Positions are 0 to 10000, unique and contiguous from zero **per
  placement**. Max 500.
- **Document media are reference-ordered.** Every `description`-placement row must be referenced at
  least once in `product.fullDescription`, and every `wiki`-placement row at least once in some wiki
  page's `content`; an unreferenced row is a 422 (`every {placement} media row must be referenced at
  least once`). References are `sulu-authoring-media://<uploadClientKey>` for new uploads and
  `sulu-media://<mediaId>` for records that already exist in the working revision. Positions must
  follow **first-reference order** across the document, scanning `fullDescription` first and then
  wiki pages in `order` (`{placement} media positions must follow first reference order`). A
  cross-placement or malformed reference is also a 422. The short `product.description` may not
  contain any media reference at all (`summary description cannot contain embedded media`).
- `versions[]`: `{scopeKey, id?, version (required, ≤128, unique), changelog? (≤1 MiB),
  compatibilityBlenderMin/Max?, extensionId?, extensionType?, extensionPlatforms?, files[]}`. Each
  version needs at least one file. Non-extension versions must not carry extension metadata;
  `blender_extension` versions need a semantic version, exactly one `main` file, a consistent
  extension id across versions, an `extensionType` of `add-on` or `theme`, and an advertised Blender
  minimum. Max 500. Prepare rejects a version with no files; validate additionally requires the
  staged file set to be **1 to 100** files and to match the declared set exactly.
- **Existing version scopes are immutable.** If a version carries an `id`, its metadata and its whole
  file set (scope keys, record ids, names, descriptions, file types, distribution kinds, tier scopes)
  must byte-match the frozen artifacts and no file may carry a new `uploadClientKey`, else 422
  `existing version {scope} file set is immutable; create a new version scope`. To change anything
  about a shipped version, add a new version scope and point `latestVersionScopeKey` at it.
- `versions[].files[]`: `{scopeKey, id? | uploadClientKey?, name, description?, fileType,
  distributionKind?, tierScopeKeys[]}`. `name` is required and ≤255, `description` ≤10000,
  `fileType` is `main`, `documentation` or `resource`. `tierScopeKeys` is **required and non-empty**
  on every file: either a subset of the declared `tiers[]` scope keys, or exactly
  `["__untiered__"]`, which is legal only when the desired catalog declares **zero** tiers (mixing
  the sentinel with real tier scopes is `file {scope} has an invalid no-tier scope`). Leave
  `distributionKind` unset: the server derives it, and a wrong value is rejected.
- `latestVersionScopeKey`: required whenever `versions[]` is non-empty, and must reference a declared
  version scope.
- `deletedScopeKeys`: `{features[], tiers[], wikiPages[], media[], versions[], files[]}`. **`desired`
  is a full replacement, not a patch**: every scope in the working revision must either be retained
  (with its exact working `id`) or listed here, else 422 `working {kind} scope {scope} must be
  retained or explicitly deleted`. A retained scope naming the wrong record is
  `retained {kind} scope {scope} must name its exact working record`; a deleted scope that is not in
  the working revision is `deleted {kind} scope {scope} is outside the exact working revision`.
- `entitlementMigration[]`: `{fromTierScopeKey, toTierScopeKey}`. This remapping is applied at **publish**, not commit.
  `from` must be an explicitly deleted tier scope (or `__untiered__` when the previous revision had
  no tiers), `to` a retained desired tier scope (or `__untiered__` when the target catalog has no
  tiers), `from != to`, sources unique. A deleted tier that still has active entitlements and no
  mapping is rejected because every active entitlement needs an explicit target.

`uploads[]` (max 500):

| field | type | notes |
| --- | --- | --- |
| `clientKey` | string | unique, bound to exactly one desired media or file |
| `purpose` | string | `avatar`, `gallery`, `description`, `wiki`, or `version_file` |
| `filename` | string | required, ≤255, no path separators, trimmed |
| `contentType` | string | canonical, ≤128 |
| `size` | int64 | ≥1, must match the uploaded bytes exactly |
| `sha256` | string | required, **`sha256:` + 64 lowercase hex** |
| `placement` | string | media only, must equal `purpose` |
| `position` | int64 | media only, must equal the media entry's `position` |
| `tierScopeKeys` | string[] | `version_file` only, must equal the bound file's set; empty for media |

Size and type limits: media images ≤25 MiB (any `image/*`), media video ≤2 GiB, `version_file`
≤5 GiB with a content type in `application/zip`, `application/x-zip-compressed`,
`application/x-rar-compressed`, `application/vnd.rar`, `application/x-7z-compressed`,
`application/gzip`, `application/x-tar`, `application/x-blender`, `application/octet-stream`.

- **Auth**: `content_write`, escalated to `catalog_admin` when the request changes commercial terms:
  `license`, `priceCents`, `blenderDonationEnabled/Pct`, `deliveryKind`, `taxCategory`,
  `compatibilityBlenderMin/Max`, `latestVersionScopeKey`, any tier, version or file set or content
  change, any `deletedScopeKeys.tiers/versions/files` entry, or any `entitlementMigration`. Deleting
  only features, wiki pages or media stays `content_write`. Creating a new product always counts as
  commercial. 403 `seller owner or admin required for pricing, license, tiers, tax, donations,
  versions, or delivery terms` on a shortfall; 403 if the org is restricted. The capability is
  re-verified **inside the commit transaction**, so losing the role mid-flow aborts the commit.
- **Response**: the operation DTO (below).
- **Conflicts (409)**: `request_digest_mismatch`, `idempotency_conflict` (key bound to a different
  digest), `draft_target_adopt_required` (same draft and digest already durable, GET or replay it),
  `draft_target_conflict`, `authoring_replay_identity_mismatch`, `working_revision_stale`,
  `authoring_prepare_conflict` (product not in this org, `catalog_provenance_state != "verified"`,
  or the product was seller-deleted). 422 on desired-state validation failures.
- **Side effects**: creates the operation, its upload slots, and for a new product a placeholder
  `products` row (`status=draft`, `catalog_provenance_state=unverified`, unique slug) **before any
  upload happens**. Abandoning a draft without `compensate` leaves that placeholder behind.
- **Idempotency keys are actor-scoped and bind permanently.** One key maps to one operation forever,
  and the digest is bound with it. Changing the desired state means a new digest, therefore a new
  key; reusing the old key is `409 idempotency_conflict`.

### Operation DTO

`{id, productId, sellerOrg, intent, phase, status, requestDigest, expectedWorkingRevision,
workingRevision, catalogSequence, slots[], result?, error?, updatedAt}`.

`slots[]`: `{id, clientKey, purpose, generation, status, progress, errorCode?, mediaId?, fileId?}`
with slot status `pending`, `uploaded`, `processing`, `ready`, `retired` or `failed`. **`generation`
is a string**, not a number, in both the slot DTO and the sign response, and it is echoed back to
`/complete` as a string. `progress` is a projection only: `uploaded`/`processing` is 75,
`ready`/`retired` is 100, anything else 0.

`result` (once a revision exists): `{productId, workingRevision, submittedRevision?,
approvedRevision?, publishedRevision?, catalogSequence, lifecycleSequence, mediaIds{clientKey→id},
fileIds{clientKey→id}, versionIds{scopeKey→id}}`.

Phases run `prepare` → `upload` → `validate` → `commit` → `finalize`; statuses run `prepared`,
`uploading`, `validating`, `validated`, `committing`, `committed`, `finalizing`, `completed`, or
`failed`, or `compensating` → `compensated`.

### POST /api/market/authoring/operations/recover

- **Body**: `{idempotencyKey, sellerOrg, draftTargetKey | productId (exactly one), requestDigest,
  expectedOperationId?}`, strictly decoded. `idempotencyKey` and `requestDigest` are required and
  must be well formed.
- **Purpose**: find a durable operation again after losing its id. The match is on actor plus
  `sellerOrg` plus locator plus idempotency-key hash plus digest and must be **unique**; identity is
  re-checked in constant time after lookup. Returns the DTO after a best-effort processing sync.
- **Errors**: `400 recovery_request_invalid`, `404 draft_target_not_found`,
  `503 authoring_recovery_unavailable` (lookup error, or an ambiguous or inexact identity match).
- Use this after a lost prepare response, or when prepare answered
  `409 draft_target_adopt_required`: that means a durable operation for this draft already exists and
  must be adopted, not recreated. The alternative is a **replay**: re-POST
  `/api/market/authoring/operations` with the same `idempotencyKey` and `requestDigest` and **no**
  `desired`.

### GET /api/market/authoring/operations/{operationId}

Poll operation state. Also drives recovery: it processes the compensation cleanup outbox and syncs
upload and media-processing state. Poll at 10 seconds or slower. Every operation route is
**actor-scoped**: an operation created by a different user is `404 authoring operation not found`,
even for another owner of the same seller org.

### POST /api/market/authoring/operations/{operationId}/uploads/{slotId}/sign

- **Preconditions**: operation in `upload`/`uploading` (a `prepared` operation auto-advances); slot
  belongs to this operation **and this actor**; slot `pending`.
- **Response**: `{slotId, generation, uploadUrl, headers, expiresAt}`. 15-minute TTL. The object key
  is server-chosen under
  `products/{productId}/files/.authoring/{operationId}/{generation}/{filename}`.
- **The `headers` map is part of the signature.** The URL is presigned with the checksum, length,
  type and creation precondition bound in, so the PUT must send every returned header verbatim or
  the request fails at storage. The set is `x-amz-checksum-sha256` (base64 of the same 32 digest
  bytes your `sha256:<hex>` describes, not the hex), `Content-Length`, `If-None-Match: *`,
  `Content-Type` and `Cache-Control: private, no-store`.
- **Write-once**: a second PUT to the same key returns 412. After a failed or uncertain PUT, call
  `/complete` (it performs the authoritative HEAD and SHA-256 probe) rather than retrying the PUT.
  A still-`pending` slot can be re-signed after the 15 minutes lapse.
- **Errors**: 409 `authoring operation is not accepting uploads`, 409 `upload slot is not pending`,
  404 `upload slot not found`, 503 `authoring storage is unavailable`, 500 signing failure.

### POST /api/market/authoring/operations/{operationId}/uploads/{slotId}/complete

- **Body**: `{"generation": "<string>"}`, strictly decoded, so a numeric `1` is `400 generation is
  required` and a wrong value is 409 `upload_generation_stale`.
- **Behavior**: the server HEADs the object and recomputes SHA-256. Any mismatch of size, type or
  hash deletes the object, fails the slot, and **fails the whole operation** with `422
  upload_identity_mismatch`. On success, a `version_file` slot creates a ready staging-scoped
  `product_files` row, and a media slot creates a `market_product_media` row with status `queued`
  for the sandboxed worker (the slot stays `processing` until variants publish). Re-completing an
  identical completed slot just re-syncs; re-completing a slot whose stored identity differs is 409
  `upload_completion_identity_stale`.

### POST /api/market/authoring/operations/{operationId}/validate

Waits for every slot to be ready, builds the staging catalog, and validates it against the live
product: revision and sequence still current, categories exist, every version's staged file set
complete and verified, media authoritatively ready, extension versions normalized. Success moves the
operation to `phase: commit`, `status: validated`. Media that is not ready yet is not an error: the
DTO stays in `upload`/`validating`, so poll. Calling it on an operation that is already failed,
completed, compensated or past `validate` is a no-op, so it is safe to re-issue while polling.
Errors: `409 working_revision_stale`, `409 authoring_operation_conflict`, or a **failed** operation
(terminal, compensate and start a fresh one) with `error.code` such as `staging_validation_failed`,
`catalog_validation_failed`, `extension_validation_failed`, `asset_processing_failed`,
`asset_processing_binding_stale`, or a media failure code.

### POST /api/market/authoring/operations/{operationId}/commit

**Irreversible.** Re-validates the staged catalog, re-verifies every storage object identity (etag,
sha256, size for files; all media variants), then in one transaction freezes a new immutable revision
(`market_product_revisions` plus artifacts and objects), applies the product projection (name, slug,
pricing, `has_tiers`, `min_price_cents`, and so on), appends the `create`/`save` lifecycle event,
sets `working_revision`, resets `review_state` to `draft`, and sets
`catalog_provenance_state=verified`. With `intent: "submit"` it also appends the `submit` event, so
the product lands in `pending_review` with `submitted_revision` set. Errors: 409
`commit_validation_failed`, `storage_revalidation_failed`, `commit_failed`, or a stale checkpoint.

### POST /api/market/authoring/operations/{operationId}/finalize

Idempotently marks a committed operation `completed`. Returns the DTO.

### POST /api/market/authoring/operations/{operationId}/compensate

- **Body** (optional): `{reason}` (≤1000). An empty body is accepted.
- Aborts and cleans up staging (staged files, media, objects, through a durable cleanup outbox)
  **only while no revision is live**. Once `phase` is `finalize` or `working_revision` is set it
  finalizes instead: immutable revisions cannot be rolled back. Terminal states are idempotent
  no-ops. Cleanup can stay queued after the call returns; a per-minute cron and `GET
  .../{operationId}` drain it and then flip the status to `compensated`.

### Delivery kinds with asynchronous pipelines

`deliveryKind: "blender_extension"`:

- The `main` file of every version must be a Blender extension `.zip`, exactly one per version, and
  its `distributionKind` resolves to `blender_extension`.
- Completing that upload enqueues an extension-sync job that normalizes the archive and runs it
  through an isolated validator producing a signed attestation. This is **asynchronous**: `validate`
  returns the operation unchanged until it finishes, so poll.
- Commit readiness requires the version not `extension_quarantined`, `delivery_status == "ready"`, a
  `canonical_file`, and a manifest whose `id` matches the product's `extension_id` and whose
  `version` matches the version label, with validator provenance whose archive SHA-256, size,
  extension id and version all agree. Failure is `error_code: extension_validation_failed`.
- **Extension identity is locked**: once `products.extension_id` is set (or
  `extension_identity_locked`), the product cannot leave `blender_extension` and no version may
  declare a different `extensionId`.
- When the main file is a fresh upload on a **new** version scope, `extensionId` and `extensionType`
  are optional (derived from the archive) but `compatibilityBlenderMin` is required. Reusing an
  existing version record requires both to be present and valid.

`deliveryKind: "blender_asset"`:

- Sources are `.blend` (`application/x-blender`) or an asset-library `.zip`; filename, declared name
  and uploaded content type must agree on the same source format.
- Compatibility is pinned: `compatibilityBlenderMin: "5.2.0"`, `compatibilityBlenderMax: "5.3.0"`.
- Each source enqueues a `market_asset_processing_jobs` row bound to this operation, slot and
  generation. Commit waits for `succeeded`; `failed`/`quarantined` fails the operation with
  `asset_processing_failed`, and a job bound to a different generation gives
  `asset_processing_binding_stale`.
- Publishing requires a validated native manifest covering **every** asset source of the latest
  version. Track progress with `GET /api/market/seller/{orgId}/assets/processing`.

---

## Product lifecycle

All four routes take the product id in the path. Submit, publish and unpublish take the optimistic
checkpoint body; delete takes none.

```json
{"expectedReviewState": "draft", "expectedPublicationState": "unpublished",
 "expectedRevision": "rev_abc123", "expectedLifecycleSequence": 4, "reason": "optional, <=1000"}
```

`expectedRevision` must equal the product's current pointer for that action. A mismatch is
`409 product lifecycle checkpoint is stale`. The product must have
`catalog_provenance_state == "verified"` and must not be tombstoned (410 if seller-deleted). Every
transition appends an immutable `market_product_lifecycle_events` row and bumps
`lifecycle_sequence`.

| action | who | pointer | precondition | result |
| --- | --- | --- | --- | --- |
| `submit` | seller `content_write` | `working_revision` | review `draft` or `rejected` | review `pending_review`; `submitted_revision` set, `approved_revision` and `rejection_reason` cleared |
| `approve` | platform admin | `submitted_revision` | review `pending_review` | review `approved`; `approved_revision` set |
| `reject` | platform admin, reason required | `submitted_revision` | review `pending_review` | review `rejected`; `rejection_reason` stored |
| `publish` | seller `catalog_admin` | `approved_revision` | review `approved`, publication `unpublished`/`unlisted`/`published`, and `working_revision == approved_revision` | publication `published`; `published_revision` and `published_at` set; entitlement remappings applied; extension versions get publication provenance |
| `unlist` | seller `catalog_admin` | `published_revision` | publication `published` | publication `unlisted`; existing buyers keep delivery |
| `suspend` | platform admin or system | `published_revision` | not already suspended | publication `suspended`; distribution suspended |
| `restore` | platform admin or system | `published_revision` | publication `suspended` | publication `unlisted` (or `unpublished` if never published); never auto-republishes |

- **POST /api/market/products/{productId}/submit** requires the working revision to resolve
  completely.
- **POST /api/market/products/{productId}/publish** additionally checks, inside the transaction,
  that the org is active, `seller_enabled` and unrestricted, and that the approved revision is
  deliverable: a frozen latest version with at least one immutable file; a `blender_extension` needs
  a validated manifest bound to its canonical file; a `blender_asset` needs complete validated native
  manifests for every latest-version asset source; and `min_price_cents > 0` requires
  `stripe_onboarding_complete` ("Stripe Connect onboarding required for paid products"). Relisting an
  unchanged approved revision from `unlisted` is legal. It does **not** check `seller_verified`, so a
  successful publish on an unverified org is still invisible to the public (see Seller state).
- **`submit` in one step**: an authoring operation prepared with `intent: "submit"` appends the
  `submit` event inside the commit transaction, so the product lands in `pending_review` with
  `submitted_revision` set and this route must not be called again for that revision.
- **POST /api/market/products/{productId}/unpublish** is registered as the `unlist` action.
- **Response** (all three): `{productId, action, status, reviewState, publicationState,
  workingRevision, submittedRevision, approvedRevision, publishedRevision, catalogSequence,
  lifecycleSequence, event: {id, sequence, revision, actorId, actorKind, created}}`.

### DELETE /api/market/products/{productId}

- **Auth**: seller `catalog_admin`. No body.
- **Behavior**: seller delete is a **tombstone, not a row delete**. A published product is first
  moved through the governed `unlist` transition, then a `market_product_tombstones` row is written.
  The product row, revisions, orders and buyer delivery all survive for existing buyers; the product
  disappears from every seller and public surface (`GET` returns 404, lifecycle routes return 410).
- **Response**: `204 No Content`, idempotent. `409 product could not be deleted safely` if the
  transactional unlist and tombstone fails.
- **Danger**: irreversible. There is no seller-facing undelete.

---

## Product media

### /api/storage/product-media (worker pipeline)

`RequireAuth`, then `verifyProductOwner` (active seller org plus `content_write`, or owner, or
platform admin).

Canonical paths:

- `POST /api/storage/product-media/upload/init`
- `POST /api/storage/product-media/upload/complete`
- `POST /api/storage/product-media/gallery/order`
- `GET /api/storage/product-media/product/{productId}`
- `POST /api/storage/product-media/product/{productId}/prune`
- `PATCH /api/storage/product-media/{mediaId}`
- `DELETE /api/storage/product-media/{mediaId}`

- **POST /upload/init**: body `{productId, placement, filename, contentType, contentLength,
  altText?}` where `placement` is `gallery`, `description` or `wiki`. Images ≤25 MiB (any
  `image/*`), everything else is treated
  as a video candidate at ≤2 GiB. Creates a `market_product_media` row (`status=uploading`, gallery
  position appended) and presigns a private write-once source upload. Response
  `{mediaId, mediaType, uploadUrl, headers, maxBytes}`, 15-minute TTL.
- **POST /upload/complete**: body `{mediaId}`. Verifies the source (HEAD, SHA-256, size ≤ declared,
  exact content type; a violation deletes the object and 400s), then queues it (`status=queued`).
  Response `202 {"ok":true,"media":{...}}`.
- **GET /product/{productId}**: owner list including pending and failed rows. Each DTO:
  `{id, placement, type, status, position, alt, width, height, duration_ms, failure_code?, src,
  srcset}` for images or `{poster, poster_srcset, sources}` for video. Poll until `ready` or
  `failed`; failure codes include `media_unsafe`, `video_undecodable`,
  `processing_attempts_exhausted`.
- **POST /gallery/order**: body `{productId, mediaIds[]}` (≤100, no duplicates, every id a non-failed
  gallery media of this product). Rewrites positions to array order. Response
  `{ok, gallery_count, updated}`.
- **PATCH /{mediaId}**: body exactly `{altText}` (≤500 runes, body ≤4096 bytes; any other key 400s).
- **DELETE /{mediaId}**: deletes the row **and its object storage source and variant objects**, renumbers the
  gallery, recomputes `gallery_count`. Response `{"ok":true}`. Permanently destroys objects.
- **POST /product/{productId}/prune**: deletes every non-gallery, non-avatar media whose
  `sulu-media://{id}` token no longer appears in `full_description` or any wiki page. Response
  `{ok, deleted}`. Bulk-destroys objects: run only after saving content.

**Where media processing actually blocks.** The authoring coordinator is the gate: `validate` will
not advance, and `commit` will not run, until every media slot the operation declares is `ready`
with verified variants, and a failed slot fails the whole operation with the media failure code. The
**registered** `submit` and `publish` routes do not re-check `market_product_media` at all; the
readiness check `productMediaReadinessBlockReason` exists only inside `handleSubmitForReview` and
`handlePublishProduct`, which are unregistered dead code (see Uncertainties). So an out-of-band
media row left `processing` or `failed` here does not block a lifecycle transition, and it also
never reaches a revision. Fix or delete it and author the change through an operation.

### /api/storage (legacy deterministic-key media and product files)

- **GET /api/storage/health**: readiness probe for authenticated users.
- **POST /api/storage/media/upload/init**: body `{productId, kind, filename, contentType,
  contentLength}` where `kind` is `avatar`, `gallery-pending`, `description` or `wiki` and
  `contentType` is `image/png`, `image/jpeg` or `image/webp`. Caps: avatar 2 MiB, gallery 10 MiB,
  description and wiki 5 MiB. Response
  `{uploadUrl, uploadIntent, objectKey, publicUrl, headers, slot?}` with a 15-minute actor-bound
  intent. The server returns deterministic object keys for each declared media purpose;
  clients must use those keys rather than construct names.
- **POST /api/storage/media/upload/complete**: body `{uploadIntent, productId?, kind?, objectKey?,
  slot?}`. Verifies the object against the signed intent (oversized objects are deleted), bumps
  `description_image_count` or `wiki_image_count` and the product `updated`.
- **POST /api/storage/media/finalize-gallery**: body `{productId, items: [{source:"existing",
  slot:N} | {source:"pending", key}]}` (≤100). Atomically copies into ordered gallery
  slots, **deletes leftovers and pending objects**, sets `legacy_gallery_count`, and
  recomputes `gallery_count`.
- **POST /api/storage/files/upload/init**: body `{productId, filename, contentType, contentLength}`.
  Creates a `product_files` row (`asset_status=pending`) and presigns a write-once PUT to
  `products/{id}/files/{uuid}/{name}` (≤5 GiB; extension products require a zip; asset products have
  their own cap and `.blend`/`.zip` source validation). Response
  `{uploadUrl, objectKey, assetId, maxBytes, headers}`.
- **POST /api/storage/files/upload/complete**: body `{assetId}`. HEAD-verifies existence, size and
  content type (violations delete the object) and marks `asset_status=ready`. Ready unlinked files
  are what `desired.versions[].files[].id` can reference. **Pending files older than 2 hours are
  garbage-collected**, as are stale `gallery/.pending/` objects.
- **POST /api/storage/files/download/init**: body `{entitlementId?, fileId}`. With an empty
  `entitlementId` this is the seller self-download path for testing your own product files. Returns
  a presigned GET with a 2-minute TTL. Buyer mode increments `products.total_downloads` and writes
  its audit row; seller self-download does neither.

`gallery_count` is `legacy_gallery_count` plus the ready pipeline gallery rows.

---

## Tiers, entitlements and wiki

Canonical paths:

- `POST /api/market/products/{productId}/tiers`
- `PATCH /api/market/products/{productId}/tiers/{tierId}`
- `DELETE /api/market/products/{productId}/tiers/{tierId}`
- `GET /api/market/products/{productId}/wiki`
- `POST /api/market/products/{productId}/wiki`
- `PATCH /api/market/products/{productId}/wiki/{pageId}`
- `DELETE /api/market/products/{productId}/wiki/{pageId}`

- **POST /api/market/products/{productId}/tiers**, **PATCH .../tiers/{tierId}**,
  **DELETE .../tiers/{tierId}**: retired. Always `409 {"code":"market_authoring_coordinator_required",
  "message":"Save this catalog change through the product authoring coordinator."}` (authorization is
  not even checked). Use `desired.tiers` and `deletedScopeKeys.tiers`.
- **GET /api/market/products/{productId}/entitlement-groups**: auth `catalog_admin`. Response
  `{"groups":[{"tier_id","tier_name","count"}],"totalCount":n}`. `tier_name` is `"No tier"` for
  untiered entitlements and `"Deleted tier"` when the tier record is gone. Use it to plan
  `entitlementMigration`.
- **GET /api/market/products/{productId}/wiki**: auth `seller_access`. Returns the **working
  revision** wiki pages sorted by `order` then id:
  `[{id, catalog_scope_key, product, title, slug, content, order, published, created, updated}]`.
  409 if the working revision cannot be resolved.
- **POST /api/market/products/{productId}/wiki**, **PATCH .../wiki/{pageId}**,
  **DELETE .../wiki/{pageId}**: retired, always 409. Author through `desired.wikiPages`. Wiki images
  go through the media pipeline with `placement: "wiki"` and are referenced in content as
  `sulu-media://{mediaId}`.

Version create, update, delete and promote endpoints do not exist as routes: version immutability
lives in the frozen revisions.

### Platform fee policy

**GET /api/market/platform-fee-policy** (public): `{policyVersion, percent, minimumCents,
minimumViablePaidPriceCents, buyerDisclosure, sellerDisclosure}`, `Cache-Control: no-store`. The
current policy is `market-platform-fee-20pct-2026-07-v1`: 20 percent with a 50 cent minimum, so the
fee is max(20 percent of product and tip proceeds, $0.50), deducted from seller proceeds rather than
added to the buyer's price. Taxes and Blender contributions are excluded from the fee base. A paid
price at or below the fee minimum fails pricing-snapshot build with `409
{"code":"market_platform_fee_minimum", ..., "minimumCents":50, "minimumViablePaidPriceCents":...}`.

**The minimum is enforced at checkout, not at authoring.** The only callers of the fee calculation
are the buyer-facing checkout and checkout-intent paths; neither the authoring coordinator nor the
publish transition looks at it. A product or tier priced at or below the minimum therefore commits,
approves and publishes normally, and then fails **every purchase attempt**. Check
`minimumViablePaidPriceCents` yourself before writing any non-free price.

**GET /api/market/contribution-policy** (public): the Blender Foundation contribution policy:
`{enabled, buyerContributionEnabled, sellerContributionEnabled, policyVersion?, beneficiary?,
disclosure?, policyUrl?, taxCode?, taxTreatment?, minimumCents: 100, maximumCents: 100000}`.

---

## Discounts

### GET /api/market/seller/{orgId}/discounts

- **Auth**: `catalog_admin` or `finance_read`. Unpaginated, `-created` order.
- **Response**: `{"page":1,"perPage":200,"totalItems":n,"totalPages":1,"items":[...]}`. Item:
  `id`, `code`, `discount_type`, `discount_value`, `visibility`, `status`, `product`, `seller_org`,
  `usage_limit`, `used_count`, `bound_email`, `expires_at`, `created`, `updated`, plus
  `expand.product` when product-scoped.

### POST /api/market/seller/{orgId}/discounts

- **Auth**: `discount_manage`. Strict JSON, ≤16 KiB, explicit `null` rejected.

| field | type | required | notes |
| --- | --- | --- | --- |
| `discount_type` | string | yes | `percentage` or `fixed_amount` |
| `discount_value` | number | yes | > 0; ≤100 for percentage; ≤1000000 and cent-precision for fixed_amount |
| `code` | string | no | uppercased and trimmed, `^[A-Z0-9][A-Z0-9_-]{2,63}$`; empty generates `PUB-XXXXXXXX` |
| `visibility` | string | no | `public` or `coupon` (default `coupon`) |
| `status` | string | no | `active`, `inactive`, `expired` (default `active`) |
| `product` | string | no | must belong to this seller; empty means seller-wide |
| `usage_limit` | int | no | 0 is unlimited, otherwise 1 to 1000000 |
| `expires_at` | string | no | RFC3339, stored as UTC |
| `bound_email` | string | no | ≤254, binds redemption to one buyer account |

- **Response**: the raw Sulu `discount_codes` record (a different shape from the GET
  projection: it also exposes `reserved_count`).
- **Errors**: 400 `discount_type and discount_value are required`, 400 with the specific validation
  message, 409 `code already exists for this seller`.
- **Side effects**: creates a redeemable coupon. Money-affecting: it lowers future buyer charges and
  seller net. It moves no money by itself.

### PATCH /api/market/seller/{orgId}/discounts/{discountId}

`discount_manage`. Partial update seeded from the stored record, same field set and validation.
`code` present but empty is `400 code cannot be empty`. `usage_limit` cannot go below
`used_count + reserved_count`; `used_count` and `reserved_count` are never client-settable. 404 when
the discount belongs to another org. Setting `{"status":"inactive"}` is the supported way to retire
a used code.

### DELETE /api/market/seller/{orgId}/discounts/{discountId}

`discount_manage`. Hard-deletes **only** when `used_count == 0`, `reserved_count == 0` and no
`market_discount_reservations` rows exist. Otherwise `409 discount has usage history and must be
deactivated instead`. Response 204.

### GET /api/market/discounts/public

Public. A bare JSON **array** (no envelope) of active public discounts with `bound_email`,
`usage_limit` and `used_count` stripped.

### POST /api/market/discount/validate

User token. Body `{code, productId, tierId?}` (strict). Response `{valid, discount_id,
discount_type, discount_value, original_price, discount, final_price}`, all cents, `final_price`
floored at 0. Errors carry the specific reason (expired, inactive, usage exhausted, wrong product,
wrong bound email; the caller's own email is used, so an email-bound code previews invalid for the
wrong account). Takes no reservation.

---

## Orders, earnings, analytics, reporting

All read-only. `analytics`, `earnings`, `reporting`, `reporting/export` and `export-sales` are
*[cash-gate]*ed. Money comes from the immutable `market_financial_ledger`; currency is **usd only**.

**Report filter** (shared by earnings, analytics, reporting and exports): `from`, `to` (RFC3339,
`from` strictly before `to`), `granularity` (`day` default, `week`, `month`, `none`), `currency`
(only `usd`, anything else 400s), `productId` (≤64 chars), `entryType` (`sale`, `refund`,
`refund_suspense`, `refund_reconciliation`, `dispute_loss`, `repair`), `search` (≤120 runes),
`perPage` (1 to 100, default 50), `cursor` or `snapshot` (opaque, ~30-minute TTL).

### GET /api/market/seller/{orgId}/orders

- **Auth**: `finance_read` or `support`. The payload is capability-shaped: `finance` only with
  `finance_read`, `customer` only with `support`, `capabilities.refund` mirrors `refund`.
- **Pagination**: **cursor only**. `page` returns `400 seller sales use cursor pagination; omit page
  and follow nextCursor`.
- **Query**: `search` (≤120 runes, matched against product name only), `status` (must be a settled
  status: `completed`, `partially_refunded`, `refunded`, `dispute_lost`; an operational status 400s
  and points at `/orders/operational`), `perPage` or `limit` (1 to 100, default 50), `since`
  (RFC3339), `cursor` or `snapshot`.
- **Response**: `{pagination:"cursor", perPage, totalItems, items[], capabilities{finance_read,
  customer_read, refund}, snapshot, nextCursor, hasMore, moneyContract,
  dataAuthority:"immutable_financial_ledger", stableSnapshot:true}`.
  Item: `id`, `product{id,name,slug,updated,gallery_count,cover_url}`, `product_version_id`,
  `product_tier`, `license_type`, `status`, `paid_at`, `refunded_at`, `created`, `updated`, plus
  `finance{gross_charge_cents, refunded_cents, net_charge_cents, product_and_tip_proceeds_cents,
  platform_fee_cents, seller_net_cents, creator_tip_informational_cents,
  buyer_contribution_payable_cents, seller_contribution_cents, tax_cents, platform_loss_cents,
  refund_suspense_cents, transfer_reversal_cents, currency, discount_code}` and
  `customer{user_id, org_id, name, email}`.
- **Snapshot semantics**: `snapshot` pins the ledger watermark, so reusing it as `cursor` gives a
  stable page set while new sales land.
- **Errors**: 400 param errors, 403, `409 seller order is missing immutable financial ledger
  evidence` (a data-integrity incident: do not retry blindly), 500. Headers: `private, no-store`.

### GET /api/market/seller/{orgId}/orders/operational

- **Auth**: `support` (not `finance_read`).
- **Purpose**: mutable in-flight workflow rows. No ledger money, no snapshot stability.
- **Query**: `search` (product name **and** customer fields here), `status` (`pending`, `failed`,
  `refund_pending`, `compensation_failed`, `disputed`; a settled status 400s and points at
  `/orders`), `page` (1 to 1000000), `perPage` or `limit` (1 to 100), `since`.
- **Response**: `{page, perPage, totalItems, totalPages, items[], pagination:"offset",
  dataAuthority:"operational_orders", stableSnapshot:false, capabilities{customer_read:true,
  refund}}`. Items always carry `customer` and never `finance`. Offset pagination, so concurrent
  inserts shift later pages.

### GET /api/market/seller/{orgId}/earnings  *[cash-gate]*

- **Auth**: `finance_read`.
- **Response**: `{available, pending, paidOut, lifetime, currency:"usd", snapshot, settlement[],
  money{}, moneyContract{}}`. `available`, `pending` and `paidOut` are summed over `settlement[]`;
  `lifetime` is `totals.seller_net_cents`.
- Each `settlement[]` entry: `seller_org_id`, `currency`, `stripe_balance_observed`,
  `stripe_balance_ambiguous`, `stripe_balance_event_ids[]`, `payout_state_ambiguous`,
  `reconciliation_available`, `pending_cents`, `available_cents`, `paid_out_cents`,
  `transfer_reversal_cents`, `seller_recovery_restoration_cents`, `seller_recovery_net_cents`,
  `economic_seller_proceeds_cents`, `unreconciled_cents`, `last_stripe_event_id`, `last_observed_at`.
  If `stripe_balance_observed` is false, or either `*_ambiguous` flag is true, the numbers are not
  authoritative and must be presented that way.
- The settlement block is a Stripe connected-account position and is **not** filtered by product,
  date or search. This endpoint cannot trigger a payout: payouts are Stripe-side.

### GET /api/market/seller/{orgId}/analytics  *[cash-gate]*

- **Auth**: `finance_read`.
- **Response**: `{totalViews, totalSales, totalRevenue, totalRevenueIncludesTips:true, avgRating,
  topProducts[], blenderDonations, tipsReceivedInformational, snapshot, money{}, moneyContract{},
  buckets[], settlement[]}`.
- `totalRevenue` is `totals.seller_net_cents` (tips included). `blenderDonations` is
  `totals.seller_contribution_cents`. `tipsReceivedInformational` is informational and already inside
  `product_and_tip_proceeds_cents`: never add it to revenue. `avgRating` is
  `organizations.seller_rating`, not ledger-derived. `topProducts[]` is
  `{productId, productName, revenue, sales, views, conversionRate}`, top 10 by seller-net revenue.
  **`totalViews` is the org lifetime sum of `products.total_views` and is never date-filtered**, so
  it will not tie out to a filtered sales figure.

### GET /api/market/seller/{orgId}/reporting  *[cash-gate]*

- **Auth**: `finance_read`.
- **Response**: `{snapshot, next_cursor, has_more, items[], totals{money}, activity_totals{},
  buckets[], settlement[], dispute_cash_by_balance_currency[], settlement_scope{kind,
  filters_applied[], filters_ignored[]}, money_contract{}, filters{}}`.
- `items[]`: `order_id`, `seller_org_id`, `product_id`, `product_tier_id`, `product_version_id`,
  `product_name`, `license_type`, `discount_code`, `currency`, `occurred_at`, `status`, `money{}`,
  `activity{}`. `money{}` is always the whole-order economics at the snapshot watermark;
  `activity{}` is what happened inside the window (`occurrence_count`, `order_count`,
  `entry_types[]`, and the `*_delta_cents` figures). The two are deliberately different.
- `buckets[]` carry **activity only**, never canonical order money; max 500.
- `settlement_scope.filters_ignored[]` names the filters that do not apply to `settlement[]`: label
  that block as an account position, not a filtered subtotal.
- **`money_contract`** (version `market-ledger-money-v2`, currency `usd`) is the machine-readable
  rule set:
  - canonical: `gross_charge_cents`, `refunded_cents`, `net_charge_cents`,
    `product_and_tip_proceeds_cents`, `buyer_contribution_payable_cents`, `seller_net_cents`,
    `platform_fee_cents`, `seller_contribution_cents`, `tax_cents`, `platform_loss_cents`,
    `refund_suspense_cents`.
  - informational, never summed with canonical: `creator_tip_informational_cents`,
    `gross_product_cents`, `transfer_reversal_cents`, `seller_recovery_restoration_cents`,
    `seller_recovery_net_cents`, `dispute_lost_economic_claim_cents`,
    `dispute_seller_recovery_claim_cents`, `seller_recovery_target_cents`,
    `unrecovered_connected_account_debt_cents`.
  - legacy aliases, never added to their canonical twin: `gross_collected_cents`,
    `exact_net_collected_cents`, `seller_proceeds_cents`, `buyer_contribution_cents`.
  - equations: `gross_charge_cents - refunded_cents = net_charge_cents`;
    `product_and_tip_proceeds_cents = seller_net_cents + platform_fee_cents +
    seller_contribution_cents`; `net_charge_cents = product_and_tip_proceeds_cents +
    buyer_contribution_payable_cents + tax_cents + platform_loss_cents - refund_suspense_cents`;
    `seller_recovery_net_cents = transfer_reversal_cents - seller_recovery_restoration_cents`.
    Dispute claims and Stripe balance cash are separate from buyer refunds and `net_charge_cents`,
    and dispute cash aggregates only within its explicit `balance_currency`.
- **Errors**: 400 (filter or cursor), 403, 503, `500 Market financial reporting is temporarily
  unavailable`. Headers: `private, no-store`.

### GET /api/market/seller/{orgId}/reporting/export  *[cash-gate]*  and  GET /api/market/seller/{orgId}/export-sales  *[cash-gate]*

- **Auth**: `finance_read`. `export-sales` is an exact alias; prefer `/reporting/export`.
- Same filter; passing a `cursor` resets the row offset so the export always starts at the beginning
  of that snapshot. `granularity` and `perPage` do not change the row set.
- **Response**: `text/csv; charset=utf-8`, delivered as an attachment. 32 columns:
  `order_id, seller_org_id, product_id,
  product_tier_id, product_version_id, product_name, license_type, discount_code, currency,
  occurred_at, status, gross_charge_cents, refunded_cents, net_charge_cents,
  product_and_tip_proceeds_cents, seller_net_cents, platform_fee_cents, seller_contribution_cents,
  buyer_contribution_payable_cents, tax_cents, platform_loss_cents, refund_suspense_cents,
  creator_tip_informational_cents, gross_product_cents, transfer_reversal_cents,
  seller_recovery_restoration_cents, seller_recovery_net_cents, dispute_lost_economic_claim_cents,
  dispute_seller_recovery_claim_cents, seller_recovery_target_cents,
  unrecovered_connected_account_debt_cents, dispute_cash_by_balance_currency_json`.
- Cells starting with `=`, `+`, `-`, `@`, a control character or a BOM are prefixed with `'`
  (CSV-injection defense). The export is spooled fully before headers are sent, so a mid-export
  failure is a clean `500`, not a truncated file. Hard cap 1,000,000 rows.

### GET /api/market/seller/{orgId}/assets/processing

- **Auth**: `content_write`. Optional `product_id` (must belong to this org, else 404).
- **Response**: `{"items":[{id, product_id, product_version_id, source_file_id, state, failure_code,
  attempt_count, asset_count, created, updated}]}`, newest first, max 200, unpaginated.

---

## Refunds and disputes

### POST /api/market/refund  *[cash-gate]*  (moves money)

- **Auth**: a member of the order's `seller_org` with refund capability
  (`owner`, `seller_admin`, or `seller_finance`).
- **Body**: `{"orderId": string}`. That is the entire contract: **there is no partial refund and no
  amount parameter.**
- **Response 200**: `{status, orderId, refundRequestId, stripeRefundId}` where `status` is the
  `market_refund_requests` status: `pending`, `requires_action` or `succeeded`.
- **Idempotency**: keyed per order (`market-full-refund:<orderId>`) plus a Stripe idempotency key.
  Re-calling while a request is `pending`, `requires_action` or `succeeded` returns the same record
  with no second Stripe call.
- **Errors**: 400 `missing orderId`; 404 `order not found`; 400 `order is not in completed status`;
  400 `refund window has expired (30 days)` (from `paid_at`); 400 `order has no payment intent (free
  order?)`; 403; **409 `the persisted refund attempt is terminal; reconcile it before retrying`**
  (the stored request is `failed` or `canceled`: needs platform reconciliation, do not retry); 502
  `refund request failed at Stripe` or `Stripe returned an incomplete refund`; 500; 503.
- **Side effects**: creates a Stripe refund with `ReverseTransfer: true`, so the buyer is refunded
  and the seller's transfer is clawed back. Order financials and buyer entitlement access change
  only when Stripe delivers `charge.refunded` with a succeeded refund. The buyer receives a Stripe
  refund receipt.

**Disputes have no write API.** They are managed through the payment provider. A
seller can only observe them through `/orders/operational?status=disputed`,
`/orders?status=dispute_lost`, and the dispute fields in reporting
(`dispute_lost_economic_claim_cents`, `dispute_seller_recovery_claim_cents`,
`dispute_cash_by_balance_currency`). Evidence is submitted in Stripe.

---

## Reviews and conversations

### POST /api/market/reviews/{reviewId}/respond

- **Auth**: the reviewed product's seller-org owner or a support-capable member.
- **Body**: `{"response": string}`, ≤10000 runes. **An empty string clears the response** and blanks
  `seller_response_at`.
- **Response**: `{"status":"ok"}`. Errors: 400 invalid body or length, 404 `review not found` (also
  when the review is not `published`), 403 `seller support access required`.
- **Side effects**: mutates the review record and writes a `review.seller_response` audit event.
  **Publicly visible to buyers.**

The other `/api/market/reviews/*` routes (create, update, delete, vote, report) are buyer-side.
`report` is available to sellers as a moderation request and hides nothing by itself.

### Conversations

Buyer access is `conversations.buyer_user`; seller access needs `support` in the conversation's
`seller_org`. All listing responses are `private, no-store`.

- **POST /api/market/conversations**: body `{productId, buyerUserId?}` (strict, ≤4 KiB). Omitting
  `buyerUserId` means the caller is the buyer (they must not be a member or owner of the seller org,
  and the product must be publicly listed or they must have an existing entitlement or order).
  Supplying it means the seller starts the thread: requires `support`, a real target user who is not
  an org member (no internal conversations) and who has an existing customer relationship. Idempotent
  per (buyer, product, seller_org). Response `{id, product, seller_org, buyer_user, status, created}`.
- **GET /api/market/seller/{orgId}/conversations**: auth `support`. Query `page` (≥1), `perPage`
  (1 to 100; `marketConversationMaxPageSize` is 100), `status` (`open`|`closed`). Paged response;
  items carry the
  conversation fields plus `role:"seller"`, `product_name`, `buyer_user_name`, `buyer_user_avatar`.
  Conversation fields: `id`, `product`, `seller_org`, `buyer_user`, `status`, `buyer_last_read_at`,
  `seller_last_read_at`, `last_message_at`, `last_message_preview`, `last_message_sender`,
  `buyer_unread_count`, `seller_unread_count`, `created`, `updated`.
- **GET /api/market/conversations/inbox**: adds `role` (`all` default, `buyer`, `seller`); merges
  buyer conversations with seller conversations across every org where the caller holds `support`
  (bounded to 100 org scopes).
- **GET /api/market/conversations/unread**: `{"buyerUnread": int, "sellerUnread": {orgId: int}}`,
  open conversations only.
- **GET /api/market/conversations/{conversationId}**: participant only. Query `page`, `perPage`;
  page 1 is the newest window, each page returned chronologically. Response
  `{conversation{...}, messages{items:[{id, sender, sender_role, body, created, seen_at, sender_name,
  sender_avatar}], page, perPage, totalItems, totalPages}}`.
- **POST /api/market/conversations/{conversationId}/messages**: participant; conversation must be
  open. Body `{"body": string}`, 1 to 5000 runes after trimming. Rate limit 20 messages per minute
  per sender per conversation (429). **Reaches a real buyer.**
- **POST /api/market/conversations/{conversationId}/read**: body `{"newestMessageId": string}`,
  must belong to the conversation. Advances the caller's watermark monotonically, recomputes unread,
  stamps `seen_at` on counterparty messages at or below it.
- **POST /api/market/conversations/{conversationId}/close**: seller `support` only (403 `only the
  seller can close conversations`). **POST .../reopen**: any participant.

---

Use the authoring coordinator and lifecycle routes documented here. Do not
infer additional capabilities.
