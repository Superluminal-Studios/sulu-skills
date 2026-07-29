# sulu-market reference (buyer side)

Complete endpoint reference for buying on Sulu Market: discovery, product reading, the
library and order history, checkout, delivery (downloads, the Blender extension
repository, the Blender asset library), reviews, conversations, and refunds.

Base URL: `https://api.superlumin.al`. Web app: `https://superlumin.al`. Auth header on
every authenticated call: `Authorization: <token>` (raw Sulu JWT from
[../sulu-api/SKILL.md](../sulu-api/SKILL.md); a `Bearer` prefix is tolerated).

**Response envelope.** `/api/market/*` endpoints return **bare JSON objects**, not the
`{"status":"success","body":{...}}` envelope used by some other Sulu custom routes.
Errors are Sulu-shaped (`{"status":409,"message":"you already own this
product","data":{}}`). The one exception in this domain is `/api/storage/...`, which
returns `{"error","message","traceId"}`; match on `error`, keep `traceId` for support.

**Money.** All amounts are integer cents, currency `usd`. Paid checkout uses Stripe
Checkout in **embedded mode**: the service returns a `clientSecret`, never a redirect
URL. Free products bypass Stripe entirely.

## Contents

- [Concepts that decide what you can see and download](#concepts-that-decide-what-you-can-see-and-download)
- [Discovery and product reading](#discovery-and-product-reading)
- [Library, purchases, receipts](#library-purchases-receipts)
- [Checkout](#checkout)
- [Delivery](#delivery)
- [Reviews](#reviews)
- [Conversations](#conversations-buyer-to-seller)
- [Flows](#flows)
- [Collections a buyer can read directly](#collections-a-buyer-can-read-directly)
- [Gotchas](#gotchas)

## Concepts that decide what you can see and download

- **Published catalog revision.** Buyer reads and downloads resolve through
  the product's published revision. An unavailable publication returns `404`.
- **Public seller status.** Products are visible only for active, verified
  sellers. Existing entitlements may continue delivering if a seller later
  becomes unavailable.
- **Subjects.** A purchase and its entitlement belong to a subject: `{type:"user"}`
  (personal) or `{type:"org", org}` (organization license, chosen with `buyerOrgId` at
  checkout). Org membership is rechecked live on every read and download, so removing a
  member kills their access immediately.
- **Entitlements are the sole delivery authority** (`entitlements`, `status = 'active'`).
  `/api/market/purchases` is an audit read-model and never grants delivery.
- **Auth kinds** used below: `public` (none), `user-token` (normal Sulu user
  token), `repo-credential` (`Authorization: Bearer mrt_...`,
  what Blender sends), `capability-URL` (a 43 char secret inside the asset-library URL,
  because Blender's remote asset libraries cannot send headers).

---

## Discovery and product reading

### GET /api/market/browse

- **Auth**: public. **Side effects**: none.
- **Purpose**: paginated, filterable list of published products.

| param | type | notes |
| --- | --- | --- |
| `category` | string | category record id |
| `subcategory` | string | category record id |
| `search` | string | substring on name and tagline, max 200 chars |
| `sort` | string | `-published_at` (default), `published_at`, `-total_sales`, `total_sales`, `-rating`, `rating`, `price_cents`, `-price_cents`, `min_price_cents`, `-min_price_cents` |
| `page` | int | >= 1 |
| `perPage` | int | 1 to 100, default 50 |

- **Response**: `{items, totalItems, page, perPage, totalPages}`. Each item: `id`,
  `seller_org`, `name`, `slug`, `tagline`, `price_cents`, `has_tiers`, `min_price_cents`,
  `delivery_kind` (`downloadable` | `blender_extension` | `blender_asset`), `rating`,
  `review_count`, `total_sales`, `status`, `published_at`,
  `compatibility_blender_min`/`_max`, `gallery_count`, `legacy_gallery_count`,
  `description_image_count`, `wiki_image_count`, `media`, `created`, `updated`,
  `expand.seller_org` (`id`, `name`, `avatar`, `seller_enabled`, `seller_verified`),
  `expand.category` and `expand.subcategories` (`{id,name,slug,icon,parent,order}`).
- **Errors**: an unknown `sort` produces `500` wrapping "published catalog sort is
  invalid". It is not a fallback: send only allowlisted values.

**Media DTO** (shared by browse, featured, related, product detail): images are
`{id, placement (gallery|description|wiki), type:"image", status:"ready", position, alt,
width, height, duration_ms, src, srcset{480,960,1440,1920}}`; videos carry `poster`,
`poster_srcset`, and `sources[{src,type,height}]` instead of `src`/`srcset`.

### GET /api/market/featured

- **Auth**: public. **Query**: optional `category` (category id).
- **Response** without `category`: `{featured, sale, newArrivals, popular}`, each an array
  of discovery items (`id, name, slug, tagline, price_cents, has_tiers, min_price_cents,
  delivery_kind, rating, review_count, total_sales, seller_org, seller_org_name, category,
  category_id, category_ids, category_slugs, subcategories, subcategory_slugs,
  gallery_count, legacy_gallery_count, media`). Sections are deduplicated in the order
  featured, newArrivals, popular. `featured` and `sale` come from admin-curated
  `featured_slots` inside their active window; `featured` falls back to the top 6 by
  `total_sales`.
- **Response** with `category`: same shape, only `featured` populated.

### GET /api/market/products/{productId}

- **Auth**: public for published products. A caller with the seller `seller_access`
  capability on the owning org gets the **working (draft) revision** instead.
- `{productId}` may be an id **or a slug** (the endpoint falls back to slug lookup).
- **Response**: `id, seller_org, name, slug, tagline, description, full_description,
  category[], subcategories[], license, price_cents, has_tiers, min_price_cents,
  blender_donation_enabled, blender_donation_pct, status, submitted_at, published_at,
  rating, review_count, total_sales, total_downloads, compatibility_blender_min/max,
  latest_version, delivery_kind, gallery_count, legacy_gallery_count (0),
  description_image_count, wiki_image_count, media, created, updated`, plus
  `expand.seller_org` (with `seller_tagline`, `bio`, `website`, `location`,
  `social_links`), `expand.category[]`, `expand.subcategories[]`, and
  `expand.latest_version` (`id, product, version, changelog,
  compatibility_blender_min/max, is_latest, extension_id, extension_type,
  extension_platforms`).
- Seller view adds authoring fields (`rejection_reason`, `working_revision`,
  `published_revision`, `review_state`, `publication_state`); buyers never see them.
- **Errors**: `404` when missing, seller-deleted, or not publicly resolvable.

### GET /api/market/products/{productId}/catalog/{kind}

- **Auth**: public for published products; sellers get the working revision.
  `kind=files` with `buyerScoped=true` requires a user token **and** an exact entitlement.
- `kind` is one of `features`, `versions`, `files`, `tiers`, `wiki`.

| param | notes |
| --- | --- |
| `ids` | comma-separated record ids to filter, max 100 |
| `versionId` | files only: restrict to that version's files |
| `buyerScoped=true` + `entitlementId` | files only: restrict to files the entitlement's tier may access. The entitlement must be active, for this product, and owned by the caller's subject |

- **Response**: `{items:[...]}`. Every item has `id, catalog_scope_key, product, created,
  updated`, plus per kind:
  - `features`: `icon, title, description, order`.
  - `versions`: `version, changelog, compatibility_blender_min/max, extension_id,
    extension_type, extension_platforms, is_latest` (latest first).
  - `tiers`: `name, description, price_cents, sort_order`.
  - `wiki`: `title, slug, content, order, published` (unpublished pages hidden).
  - `files`: `product_version, product_tier[] (tier ids), tier_scope_keys[], name,
    description, file_type, distribution_kind, asset_status, archive_hash,
    extension_sync_status, extension_sync_error, file_size, archive_size, object_key:""`
    (the object key is only populated for seller view).
- **Caching**: `public, max-age=60` for anonymous reads; `private, no-store` for seller or
  buyer-scoped reads.
- **Errors**: `404` unknown kind or product; `400` bad ids; `401`/`403` buyer-scoped
  without a valid exact entitlement; `409` when the entitlement's tier is outside the
  published catalog.

### GET /api/market/products/{productId}/related

- **Auth**: public. **Response**: `{related:[...]}`, discovery items plus `match_reason`
  (`same_seller` | `same_category` | `popular`), `matched_category_ids`,
  `matched_category_slugs`. Three tiers: up to 6 from the same seller, up to 6 from the
  same category or subcategory at other sellers, then a popular fallback.
- **Errors**: `404` when the product is not resolvable as published.

### POST /api/market/products/{productId}/view

- **Auth**: optional (attributed to the user when a token is present).
- **Response**: `{tracked: true|false}` (`false` means already counted today; dedup is per
  hashed IP per day).
- **Side effects**: inserts a `product_views` record and increments
  `products.total_views`. Web-UI telemetry: an agent has no reason to call it.

### GET /api/market/sellers/{orgId}

- **Auth**: public. **Response**: `{id, name, avatar, slug, tagline, bio, website,
  location, social_links, verified, rating, review_count, total_sales,
  blender_donation_enabled, blender_donation_pct, products:[...]}` (up to 100 products,
  sorted by sales, browse-style summaries including `media`).
- **Errors**: `404` if the org is missing or not a public seller.

### GET /api/market/discounts/public

- **Auth**: public. **Response**: a JSON array of `{id, code, discount_type
  (percentage|fixed_amount), discount_value, visibility, status, product, seller_org,
  expires_at, expand{product{id,name,slug}, seller_org{id,name}}}`. Usage counters and any
  bound email are deliberately omitted from the public shape.

### GET /api/market/contribution-policy

- **Auth**: public. `Cache-Control: no-store`.
- **Response**: `{enabled, buyerContributionEnabled, sellerContributionEnabled}`, and when
  enabled also `policyVersion, beneficiary, disclosure, policyUrl, taxCode, taxTreatment,
  minimumCents (100), maximumCents (100000)`.

### GET /api/market/platform-fee-policy

- **Auth**: public. `Cache-Control: no-store`.
- **Response**: `{policyVersion, percent, minimumCents, minimumViablePaidPriceCents,
  buyerDisclosure, sellerDisclosure}`. Echo `policyVersion` back at checkout as
  `expectedPlatformFeePolicyVersion`; a mismatch is `409` ("platform fee policy
  changed...").
- **Errors**: `503` when not configured.

---

## Library, purchases, receipts

### GET /api/market/library

- **Auth**: user-token. `Cache-Control: private, no-store`.
- **Purpose**: the buyer's library, one item per **active entitlement**. Cursor-paginated
  and stable: this is the ownership authority.

| param | notes |
| --- | --- |
| `perPage` | 1 to 100, default 50 |
| `cursor` | opaque, from `nextCursor` |
| `subjectType` | `""` (personal plus all my orgs), `user`, or `org` |
| `orgId` | required when `subjectType=org`; membership checked live |
| `productId` | filter to one product, max 64 chars |

- **Response**: `{page:1, perPage, totalItems, totalPages, nextCursor, hasMore, items:[]}`.
  Item: `entitlementId, productId, productTierId?, licenseType, subjectType, subjectId,
  grantedAt?, product?`. `product`: `{id, name, slug, tagline?, status, deliveryKind,
  distributionKind?, extensionId?, assetIds[], sellerOrgId, seller{id,name,avatar?,
  verified}?, categories[{id,name,slug,icon?}], latestVersion{id,version,
  blenderVersionMin?,blenderVersionMax?,created?}?, thumbnail?, galleryCount, updated?,
  priceCents, minimumPriceCents, rating, reviewCount, license, blenderVersionMin?,
  blenderVersionMax?}`. `assetIds` is scoped to the exact entitlement's tier and never
  leaks another tier's assets; object keys and hashes never appear here.
- **Errors**: `403` "not authorized for this organization library"; `400` bad cursor,
  "orgId is required for an organization library", "subjectType must be user or org";
  `409` "organization subject set exceeds the supported limit" (the caller belongs to more
  orgs than the unscoped query can fan out over: rerun with an explicit
  `subjectType=org&orgId=...`).
- `page` is hard-coded to `1` in the envelope: pagination is cursor-only. Also sets
  `Pragma: no-cache` alongside `Cache-Control: private, no-store`.

### GET /api/market/purchases

- **Auth**: user-token (must be a `users`-collection token). `private, no-store`.
- **Purpose**: order history, an audit read-model. Never delivery authority.

| param | notes |
| --- | --- |
| `subjectType` | `user` (default) or `org` |
| `subjectId` | required for `org`; for `user` it must equal the caller's own id if sent |
| `page` | 1 to 1,000,000 |
| `perPage` | 1 to 100, default 50 |
| `search` | product-name substring, max 120 chars |
| `status` | `pending, completed, failed, refunded, partially_refunded, refund_pending, compensation_failed, disputed, dispute_lost, adjustment` |

- **Org access**: org history requires the org owner or a role in `{admin, manager,
  seller_admin, seller_finance}`. Plain entitlement membership is not enough.
- **Response**: `{page, perPage, totalItems, totalPages, items:[{id, subject_type,
  subject_id, product{id,name,slug,updated,gallery_count,cover_url}, product_tier{id,name}?,
  seller{id,name,slug,verified}, amount_cents, tip_cents, contribution_cents, currency,
  license_type, status, paid_at, refunded_at, created, updated, receipt_available}]}`.
  Personal history excludes org purchases even when the caller completed that checkout.
- Offset pagination over mutable rows: totals drift between pages. Prefer the library for
  ownership questions.

### GET /api/market/orders/{orderId}/receipt

- **Auth**: user-token; only when `orders.buyer_user == auth.id`.
- **Preconditions**: order status in `{completed, refund_pending, compensation_failed,
  partially_refunded, refunded, disputed}` (evidence survives refunds and disputes).
- **Response**: any of `{receipt_url, hosted_invoice_url, invoice_pdf}`, present only when
  available.
- **Errors**: `404` order or evidence missing; `403` not your order; `400` no completed
  payment.

### GET /api/market/legacy-purchases

- **Auth**: user-token, same subject resolution and org-role gate as `/purchases`.
- **Purpose**: read-only claims from the legacy marketplace. Immutable, with no
  delivery authority.
- **Query**: `page`, `perPage`, `search`, `status` as above.
- **Response**: `{page, perPage, totalItems, totalPages, items:[{id, legacy_order_id,
  legacy_entitlement_id?, subject_type, subject_id, seller_org_id, product{...},
  product_tier{...}?, amount_cents, currency, license_type, order_status,
  entitlement_status, paid_at, created, updated, delivery_authority:false, claim_state,
  regrant_status, receipt_available, message}], dataAuthority:"legacy_purchase_claim",
  deliveryAuthority:false}`.

---

## Checkout

**Idempotency.** Paid and free checkout accept an idempotency key in the body
(`idempotencyKey`) or the `Idempotency-Key` header; if both are present they must match
(`400` otherwise). The key binds buyer plus key to one durable `market_checkout_intents`
row with a request fingerprint. Replaying with a different cart is `409` ("idempotency key
is already bound to a different checkout"). Checkout intents expire after **45 minutes**.

The key is **required**, not optional, and must be 8 to 200 visible ASCII characters
(`normalizeMarketIdempotencyKey`). Omitting it does not produce a helpful `400`: on
`POST /api/market/stripe/checkout` the error escapes as `500 "failed to initialize
checkout"`, and on `POST /api/market/stripe/checkout-free` as `409 "completed free
checkout could not be verified"`. Always send one.

**Two 503 service gates** wrap the financial routes and can refuse an otherwise valid
request. `{"code":"market_stripe_payments_disabled","retryable":true}` is the paid-checkout
kill switch. `{"code":"market_identity_cash_repair_required","retryable":true}` is the
identity/cash reconciliation freeze (`marketIdentityCashFinancialSurfaceGate`) and guards
`checkout`, `checkout-free`, `verify-session`, `cancel-checkout`, and `refund` alike.
Neither means the request was malformed; both are retryable later, not in a loop.

### POST /api/market/discount/validate

- **Auth**: user-token. **Side effects**: none (preview only).
- **Body** (strict JSON, max 16 KB, no unknown or duplicate fields): `{code, productId,
  tierId?}`. Codes are canonicalized to upper case and must match
  `^[A-Z0-9][A-Z0-9_-]{2,63}$`.
- **Response**: `{valid:true, discount_id, discount_type ("percentage"|"fixed_amount"),
  discount_value, original_price, discount, final_price}` (cents; a `fixed_amount`
  `discount_value` is a dollars-with-cents float, converted server-side).
- **Errors**: `404` product or invalid code; `400` invalid body, expired, usage limit
  reached, wrong product, wrong bound email, invalid tier.

### POST /api/market/stripe/checkout

**Spends money.** Needs the human's explicit approval of this product, tier, and price.

- **Auth**: user-token. Gated by `marketStripePaymentsEnabled()`: when payments are
  disabled the response is `503 {code:"market_stripe_payments_disabled", retryable:true}`,
  and by the identity-cash gate
  (`503 {code:"market_identity_cash_repair_required", retryable:true}`).
- **Body decoding is lenient** here (plain `json.Decoder.Decode`): unknown fields are
  silently dropped rather than rejected, unlike the review, conversation, discount, and
  drag-link bodies. A typo in a field name fails as a missing value, not as a `400`.

| field | type | notes |
| --- | --- | --- |
| `productId` | string | required |
| `tierId` | string | required when the product `has_tiers` |
| `discountCode` | string | user-entered coupon; invalid is `400` |
| `publicDiscountId` | string | site campaign; silently ignored when invalid |
| `buyerOrgId` | string | buy an organization license; must be an active org the caller owns or belongs to |
| `tipCents` | int | 0, or 100 to 100000 |
| `buyerDonationCents` | int | 0, or 100 to 100000 |
| `idempotencyKey` | string | **required**, 8 to 200 visible ASCII chars (or the `Idempotency-Key` header) |
| `expectedPlatformFeePolicyVersion` | string | **required**: `400` "expectedPlatformFeePolicyVersion is required for paid checkout" when absent, `409` on mismatch. Read it from `/platform-fee-policy` first |

- `discountCode` and `publicDiscountId` are both evaluated and the **larger** discount
  applies. They never stack.
- **Validation sequence**: product published and catalog resolvable, tier belongs to the
  exact revision, seller public and Stripe payment-eligible, **self-purchase blocked**
  (owner or member of the seller org, or buying "as" the seller org, is `400`), buyer-org
  membership, already-owned check (`409` "you already own this product"/"this tier").
- **Free after discount**: when the discount brings the price to 0 with no tip or
  donation, the endpoint short-circuits into the free-order path and answers like
  `checkout-free`.
- **Response is a union.** Branch on which keys came back, never on the HTTP status:
  `{intentId, sessionId, clientSecret, status, expiresAt}` means "mount Stripe", while
  `{orderId, entitlementId, status:"completed"}` means the discount zeroed the price and the
  order already exists (skip straight to the library).
- **Response**: `{intentId, sessionId, clientSecret, status, expiresAt}`.
  `clientSecret` is for embedded Checkout. Use the browser state returned by
  the supported checkout flow; do not construct a return URL.
  Re-POSTing with the same key while the session is open returns the same session; once it
  is no longer open the answer is `409` "checkout session is no longer open; start a new
  purchase attempt".
- **Errors**: `400` (missing or invalid inputs, "use checkout-free for free products",
  subtotal below 50 cents gives "total amount too low for payment processing"), `409`
  (already own, policy version changed, discount usage limit reached, intent conflict,
  authorization changed mid-flight), `502` (Stripe create or retrieve failed), `503`
  (payments disabled, Stripe Tax not ready, tax evidence storage unconfigured).
- **Side effects**: creates a durable `market_checkout_intents` row (may reserve discount
  capacity) and a Stripe Checkout Session. The charge itself happens when the human
  completes the embedded form.

### POST /api/market/stripe/checkout-free

**Creates a real order and entitlement.** Needs approval even though it is free.

- **Auth**: user-token. Works even when paid checkout is globally disabled, as long as no
  tip or donation is attached. The identity-cash gate still applies.
- **Body**: `{productId (required), tierId?, buyerOrgId?, tipCents?, buyerDonationCents?,
  idempotencyKey (required), expectedPlatformFeePolicyVersion}`. No discount fields.
  `expectedPlatformFeePolicyVersion` is only checked on the tip/donation path, where it is
  required exactly as in paid checkout; a pure free claim ignores it. Decoding is lenient.
- **Behavior**: the product or tier effective price must be 0 (else `400` "product is not
  free"). With `tipCents > 0` or `buyerDonationCents > 0` this becomes a Stripe embedded
  session exactly like paid checkout, and tips additionally require a Stripe-ready seller
  (`400` "seller is not ready to receive creator tips"); the response is then
  `{intentId, sessionId, clientSecret, status, expiresAt}`. Otherwise order and
  entitlement are created synchronously in one transaction that revalidates publication,
  seller public status, self-purchase, org membership, license, and price still 0.
- **Response (pure free)**: `{orderId, entitlementId, status:"completed"}`. Idempotent
  replays and already-owned races return the same with `alreadyOwned:true` (200), or `409`
  "you already own this product or tier through a different checkout".
- **Side effects**: creates `orders` (status `completed`, amount 0), `entitlements`
  (active), a `sale` row on the immutable financial ledger, and bumps product sales
  counters via the outbox.

### POST /api/market/stripe/verify-session

- **Auth**: user-token; the session must belong to the caller (checked against the
  intent's `buyer_user`, with a legacy fallback to session metadata `buyerUserId`), else
  `403`. Identity-cash gate applies.
- **Body**: `{sessionId}`. Missing it is `400` "missing sessionId"; a Stripe lookup failure
  is `502` ("failed to verify session with Stripe" / "failed to verify payment evidence
  with Stripe").
- **Response**: `{status:"pending"}` while Stripe reports unpaid; `{status:"completed",
  orderId}` after fulfillment; when an order already exists for the session,
  `{status:<order.status>, orderId}`.
- **Side effects**: idempotently fulfills the order (order, entitlement, ledger rows) when
  the payment provider reports success but Sulu has not reflected it yet.
  Poll at 10 seconds or slower.

### POST /api/market/stripe/cancel-checkout

- **Auth**: user-token; `intent.buyer_user` must be the caller (else `403`). Identity-cash
  gate applies.
- **Body**: `{intentId}` -> `{intentId, status:"cancelled"}`.
- **Side effects**: expires the Stripe session and terminalizes the local intent,
  releasing any discount reservation.
- **Errors**: `404` intent; `409` completed or not cancellable; `502` Stripe verify or
  expire failed.

## Delivery

### POST /api/storage/files/download/init

- **Auth**: user-token (the whole `/api/storage` group requires auth).
- **Purpose**: mint a short-lived presigned URL for a manual download of a purchased file.
- **Body**: `{entitlementId, fileId}`. Omitting `entitlementId` is the seller
  self-download path for their own file, not a buyer flow.
- **Authorization**: the entitlement must be active and owned by the caller's subject
  (live org-membership check); the file must belong to the entitled product, have
  `asset_status = 'ready'`, exist in an entitled immutable published revision, match the
  entitlement's tier scope, and satisfy the per-kind rule: extensions only the canonical
  archive of the exact current version with a published manifest; blender_assets only the
  current version's source with all normalized assets deliverable; plain downloadables
  require product status `published` or `unlisted`.
- **Response**: `{download: {url, expiresAt, filename}}`, a presigned GET valid **2
  minutes** with `Content-Disposition: attachment`. Fetch it with a plain unauthenticated
  `GET`: the URL carries its own object storage signature, so no `Authorization` header belongs on it.
- **Errors** (`{error, message, traceId}`): `404` entitlement or file; `403` not yours or
  not currently authorized; `400` not ready; `503` storage unconfigured.
- **Side effects**: increments `products.total_downloads`, writes a `downloads` audit row
  (hashed IP and UA), stamps `entitlements.last_downloaded_version`. Do not poll.

### Blender asset metadata and previews (web UI)

| endpoint | auth | notes |
| --- | --- | --- |
| `GET /api/market/products/{productId}/assets` | public | Public normalized assets of the latest published version of a `blender_asset` product. `{items:[{id, name, id_type, preview_url?, catalog{id,name}, metadata{description,author,license,copyright,tags,properties}, compatibility{blender_min, blender_max?}}]}`. `404` unless it is a published, distribution-active blender_asset from a public seller. |
| `GET /api/market/products/{productId}/assets/{assetRecordId}/preview.png` | public | Streams the PNG with exact size and SHA-256 verification. Supports `If-None-Match`/`ETag` (`"sha256hex"`). |
| `GET /api/market/library/{entitlementId}/assets` | user-token | Owned assets for one active entitlement, tier-scoped, live membership check. `{entitlement_id, product_id, buyer_subject{kind: personal|organization, org_id?}, items:[...]}`, `private, no-store`. `404` for invalid or foreign entitlements; `503` when the version exceeds the delivery cap. |
| `GET /api/market/library/{entitlementId}/assets/{assetRecordId}/preview.png` | user-token | Streams an owned preview; entitlement, publication, and object identity are re-verified before headers and during the stream. `404` on any failure. |

### Extension repository v2

Personal repository model: each user has at most one active `user_library` repository
credential (an `mrt_...` bearer). Blender is configured with the repository URL and
"Requires Access Token" set to that credential. Older per-device credentials keep working
until regeneration. The subject may also be an org, using an org-scoped credential.

#### GET /api/market/extensions/repository-credential

- **Auth**: user-token. `no-store`.
- **Response**: `{credential: {id, repositoryUrl, accessToken ("mrt_..."), created,
  lastUsedAt|null} | null, replacementRequired: bool}`. `repositoryUrl` is
  `{base}/api/market/extensions/repo/v2/user/{userId}/index.json`. This reveals the raw
  token (stored encrypted server-side): treat it as a secret.

#### PUT /api/market/extensions/repository-credential

- **Auth**: user-token. **Response**: same shape with a fresh token.
- **Side effects**: **revokes every previously active repo credential the user created or
  owns, including device credentials.** Existing Blender installs must be reconfigured, so
  confirm with the human before rotating an existing credential.
- **Errors**: `429` with `Retry-After: 3600` on the hourly issuance limit.

#### GET /api/market/extensions/repo/v2/{subjectType}/{subjectId}/index.json

- **Auth**: `repo-credential` only (`Authorization: Bearer mrt_...`); the credential's
  subject must match the URL subject (`401` invalid, `403` mismatch). No Sulu user
  token is involved: this is the call Blender makes, not you.
- **Query**: `platform`, `blender_version`, `python_version` (Blender sends these to
  filter compatible builds; device credentials persist the observed target).
- **Response**: `{version:"v1", blocklist:[{id, reason}], data:[{schema_version:"1.0.0",
  id, name, tagline, version, type, maintainer, license[], website?, tags?, platforms?,
  python_versions?, copyright?, permissions?, blender_version_min, blender_version_max?,
  archive_url, archive_hash ("sha256:..."), archive_size}]}`. Hard cap 500 entries (`409`
  above it). `ETag` (`"sha256-..."`), `If-None-Match`/`304`, `Cache-Control: private,
  max-age=60`.
- **Side effects**: stamps the credential's `last_used_at` and UA.

#### GET /api/market/extensions/archive/v2/{subjectType}/{subjectId}/product/{productId}/version/{versionId}.zip

- **Auth**: `repo-credential` matching the URL subject.
- **Behavior**: the product must be an extensions-category product, the version must
  belong to it, and the subject must hold a live entitlement selecting an installable
  canonical file (`403` "subject is not entitled to this product"). Entitlement,
  quarantine, and distribution authority are re-verified **every second during the
  stream**: revocation mid-download aborts it.
- **Errors**: `404` product or version; `403` not entitled; `409` archive not deliverable.

#### POST /api/market/extensions/drag-link

- **Auth**: user-token. **Body** (strict JSON): `{productId, versionId}` (a `.zip` suffix
  on `versionId` is tolerated).
- **Response**: `{dragUrl, repositoryUrl, productId, versionId, expiresAt:null}`.
  `dragUrl` is the personal v2 archive URL with `repository`, `blender_version_min/max`,
  `platforms`, and `python_versions` query params.
- **Errors**: `409 {code:"repository_setup_required"}` when the user has no repository
  credential yet; `403` when the extension is not in the caller's repository; `409` not
  deliverable.

#### POST /api/market/extensions/repo/preflight

- **Auth**: user-token; the caller must be authorized for the target subject.
- **Body**: `{subjectType ("user"|"org") required, orgId?, productId?, versionId?, platform?,
  blenderVersion?, pythonVersion?}`. `subjectType` has no default: omitting it is `400`
  "subjectType is required", `"user"` with an `orgId` is `400`, and `"org"` without one is
  `400`. Omitting `productId` returns `ok` for the repository as a whole plus `itemCount`.
- **Always HTTP 200** for a resolved subject: success lives in the body's `ok`/`reason`. The
  only real HTTP errors are `400` (bad subject) and `403` ("not authorized for the target
  repository subject").
- **Response**: `{ok, reason, repositoryUrl, subjectType, subjectId, orgId?, productId,
  versionId, expectedArchiveUrl, requiresAccessToken:true, actions[], itemCount,
  tokenLastUsedAt, tokenLastUsedUa, tokenExpiresAt}`. `reason` is one of `ok`,
  `repository_credential_required`, `index_unavailable`, `product_not_found`,
  `product_not_extension`, `no_entitlement`, `version_not_found`, `no_installable_file`,
  `incompatible_blender_version`, `incompatible_platform`, `incompatible_python_version`,
  `not_in_index`, plus preparing and failed sync states. `actions` are human-readable
  remediation steps: relay them, do not invent your own.

### Blender private asset library

A capability-URL protocol: Blender's remote asset libraries cannot send auth headers, so
the secret lives in the URL path. **The library URL is itself a credential.** The server
redacts it from logs; you should never print or share it.

#### GET /api/market/assets/library-credential

- **Auth**: user-token.
- **Response**: `{credential: {id, name ("Sulu Blender Asset Library"), libraryUrl,
  created, lastUsedAt|null} | null, replacementRequired}`. `libraryUrl` is
  `{origin}/api/market/assets/library/v1/{43-char-capability}/`.
  `replacementRequired:true` means an old-format credential exists whose URL can no longer
  be revealed: regenerate.

#### PUT /api/market/assets/library-credential

- **Auth**: user-token. Rotates the library URL and **revokes all previous active library
  credentials** for that user. `429` with `Retry-After: 3600` on the hourly limit.

#### Capability-authenticated protocol (Blender calls these, no user token)

Base `/api/market/assets/library/v1/{capability}/`:

- `GET /api/market/assets/library/v1/{capability}/_asset-library-meta.json`
- `GET /api/market/assets/library/v1/{capability}/_v1/asset-index.json`
- `GET /api/market/assets/library/v1/{capability}/_v1/pages/{page}`
- `GET /api/market/assets/library/v1/{capability}/_v1/previews/{filename}`
- `GET /api/market/assets/library/v1/{capability}/_v1/files/{filename}`

- The metadata response returns the versioned index URL and hash, library
  name, and contact data. It materializes a **10 minute snapshot** of everything
  the user's active entitlements allow. Rate limit 60/min per credential
  (`429` with `Retry-After: 60`).
- The index response returns schema version, aggregate sizes/counts, page URLs
  and hashes, and catalog paths/identifiers, pinned to the snapshot revision
  named by `hash`.
- `_v1/pages/{page}?hash=...` (page is zero-padded to 5 digits) -> `{asset_count,
  file_count, assets:[{name, id_type, files[], bl_versions{min,until?},
  thumbnail{url,hash}?, meta{...}?}], files:[{path, size_in_bytes, hash, blender_version,
  url}]}`.
- `_v1/previews/{slug}.png?hash=...` and `_v1/files/{slug}.blend?hash=...` -> streamed
  bytes with exact SHA-256 and size verification; entitlement and publication authority
  are re-verified before headers and continuously during the stream.
- Query strings are allowlisted per route (`s` on the meta document, `s` and `hash`
  everywhere else). Any other key, a repeated key, or a value over 128 chars is a `404`, so
  never append tracking or cache-busting params to a library URL.
- All failures surface as `404` ("asset library not found") so the response never confirms
  whether a capability is valid; `503` when snapshot materialization fails. Headers:
  `private, no-store`, `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex`.

The exact extension archive route is
`GET /api/market/extensions/archive/v2/{subjectType}/{subjectId}/product/{productId}/version/{versionId...}`.
Blender calls it with its repository credential; an agent never prints or proxies the
archive body.

---

## Reviews

Reviews are **read** through the Sulu records API and **written** through custom
routes. Mutation bodies are strict JSON: unknown fields rejected, max 64 KB, exactly one
JSON value. A review is bound to a license subject (personal or org) and requires purchase
proof: an active entitlement whose linked order (if any) matches the subject and is
`completed` or `partially_refunded`.

GUARDRAILS section 4 applies to everything in this section: no self-reviews, no vote
brigading, no incentivized or reciprocal reviews, no reviews of products the account has
not genuinely used, no reports aimed at competitors.

### POST /api/market/products/{productId}/reviews

- **Auth**: user-token.
- **Body**: `{rating (int 1 to 5), title (max 200 runes), body (max 10000 runes),
  subjectType ("user"|"org"|omitted), orgId (required iff subjectType="org")}`. With
  `subjectType` omitted the server searches the personal subject plus every org; if more
  than one subject owns the product it answers `409` "multiple license subjects own this
  product; select a personal or organization license".
- **Response**: `{id, subjectType, subjectId}`.
- **Errors**: `404` product; `409` product not published-for-review, subject already
  reviewed, or duplicate proof needing support; `403` "you must own this product to review
  it" or not authorized for the org.
- **Side effects**: creates a `reviews` record (status `published`, `authority_state:
  verified`), recalculates product and seller rating aggregates, appends a
  `market_review_events` audit row.

### PATCH /api/market/reviews/{reviewId}

- **Auth**: user-token, author only (`403` "you can only modify your own reviews"), and the
  entitlement or order proof must still verify (org reviews also require current org
  membership; the entitlement itself no longer has to be `active`). `404` "review not found".
- **Body**: `{rating (1 to 5), title, body}`. Only `rating` is validated; `title` and `body`
  are bounded but may be empty. **This is a full replacement**, so a body that omits `title`
  or `body` writes them as empty strings and silently wipes the existing text. Always resend
  all three fields.
- **Response**: `{id}`. Recalculates ratings and writes an audit event.

### DELETE /api/market/reviews/{reviewId}

- **Auth**: user-token, author only. **Response**: `204 No Content`.
- **Side effects**: deletes the review and its votes, resolves open reports, recalculates
  ratings, audit event. Destructive: name the review to the human and get a yes first.

### POST /api/market/reviews/{reviewId}/vote

- **Auth**: user-token. Voting on your own review is rejected.
- **Body**: `{vote: "up" | "down" | null}` (null removes the caller's vote).
- **Response**: `{helpful_count, user_vote}`; `helpful_count` is sum(up minus down),
  floored at 0.
- **Side effects**: upserts or deletes a `review_votes` row, updates
  `reviews.helpful_count`, audit event.

### POST /api/market/reviews/{reviewId}/report

- **Auth**: user-token. Reporting your own review is rejected, and members or the owner of
  the product's seller org cannot report reviews on their own products.
- **Body**: `{reason (required, max 1000 runes)}`.
- **Response**: `{status: "reported" | "already_reported"}` (idempotent per reporter).
- **Side effects**: creates a private `market_review_reports` row, sets
  `reviews.reported = true`, audit event. Use it for genuine abuse only.

### POST /api/market/reviews/my-votes

- **Auth**: user-token. **Body**: `{reviewIds: [string]}` (max 100 ids, each max 64
  chars). **Response**: an array of `{id, review, user, vote}` for rendering vote state.

### POST /api/market/reviews/{reviewId}/respond (seller, not a buyer action)

- **Auth**: user-token with the seller `support` capability on the product's seller org.
  Listed only because buyers see `seller_response` and `seller_response_at` on reviews.

---

## Conversations (buyer to seller)

All conversation routes need a user token, and most require a `users`-collection auth
record. Bodies are strict JSON (unknown or duplicate fields rejected), messages are at most
5000 runes, and the rate limit is **20 messages per minute per sender per conversation**
(`429`).

### POST /api/market/conversations

- **Body**: buyer form `{productId}`. (The seller form `{productId, buyerUserId}` requires
  seller `support` capability and an existing customer relationship.)
- **Buyer constraints**: you cannot message your own product (seller-org member or owner
  gets `400`). For a product that is not publicly visible you need a purchase relationship
  (active entitlement, a past order in a paid lifecycle status, or an org entitlement),
  else `403` "this product is not available for new conversations".
- **Response**: `{id, product, seller_org, buyer_user, status ("open"), created}`, `200`
  whether it was created or already existed.

### GET /api/market/conversations/buyer

- **Query**: `page` (>= 1), `perPage` (1 to 100, default 50), `status` (`open`|`closed`).
- **Response**: `{page, perPage, totalItems, totalPages, items:[conversation + role:"buyer"
  + product_name + seller_org_name + seller_org_avatar]}`. The conversation map is
  `{id, product, seller_org, buyer_user, status, buyer_last_read_at, seller_last_read_at,
  last_message_at, last_message_preview, last_message_sender, buyer_unread_count,
  seller_unread_count, created, updated}`. `private, no-store`.

### GET /api/market/conversations/inbox

- **Query**: `page`, `perPage`, `status`, `role` (`all` default, `buyer`, `seller`).
- **Response**: the same page shape, each item carrying `role` and the matching
  perspective's expansions. Combines buyer-side threads with seller-side threads for orgs
  where the caller holds `support`.

### GET /api/market/conversations/unread

- **Response**: `{buyerUnread: int, sellerUnread: {orgId: int}}`, open conversations only.

### GET /api/market/conversations/{conversationId}

- **Auth**: participant only (the buyer, or a seller-org member with `support`), else
  `403`.
- **Query**: `page`, `perPage` page the **messages**, newest page first, each page in
  chronological order.
- **Response**: `{conversation:{...conversation map, role, product_name, buyer_user_name,
  buyer_user_avatar, seller_org_name, seller_org_avatar}, messages:{items:[{id, sender,
  sender_role ("buyer"|"seller"), body, created, seen_at, sender_name, sender_avatar}],
  page, perPage, totalItems, totalPages}}`.

### POST /api/market/conversations/{conversationId}/messages

- **Body**: `{body}` (trimmed, required, max 5000 runes). **Response**: the created
  message. **Errors**: `400`/`409` conversation closed; `429` rate limit.
- **Side effects**: updates the conversation preview and `last_message_*`, and the other
  side's unread counter. This reaches a person: draft, confirm, then send.

### POST /api/market/conversations/{conversationId}/read

- **Body**: `{newestMessageId}`, the newest message actually rendered. The watermark never
  moves backwards. **Response**: `{ok:true, newestMessageId, read_at}`.
- **Side effects**: recomputes the caller's unread count and stamps `seen_at` on the other
  side's messages up to the watermark.

### POST /api/market/conversations/{conversationId}/close

- **Auth**: seller org `support` only. Buyers get `403` "only the seller can close
  conversations".

### POST /api/market/conversations/{conversationId}/reopen

- **Auth**: any participant, buyer included. **Response**: `{status:"open"}`.

---

## Flows

**1. Browse to product page.** `GET /api/market/featured` or `/browse` ->
`GET /api/market/products/{idOrSlug}` -> `/catalog/features|versions|tiers|wiki` ->
reviews via `GET /api/collections/reviews/records?filter=(product='...')&sort=-created`
(then `POST /api/market/reviews/my-votes` when signed in) -> `/related`. For
`blender_asset` products also `GET /api/market/products/{id}/assets`.

**2. Paid checkout.** `GET /api/market/platform-fee-policy` (not optional: keep
`policyVersion`) -> optional `POST /api/market/discount/validate` ->
`POST /api/market/stripe/checkout` with `idempotencyKey` **and**
`expectedPlatformFeePolicyVersion` -> mount embedded Checkout with `clientSecret` -> on
return `POST /api/market/stripe/verify-session` until `{status:"completed", orderId}` ->
`GET /api/market/library?productId={id}` for the `entitlementId`. Abandon with
`POST /api/market/stripe/cancel-checkout`. Re-POSTing checkout with the same key resumes
the same open session; a `409` means start a fresh attempt with a new key. If the response
carries `orderId`/`entitlementId` instead of a `clientSecret`, a discount zeroed the price:
skip the Stripe steps.

**3. Free checkout.** `POST /api/market/stripe/checkout-free {productId, tierId?,
buyerOrgId?, idempotencyKey}` -> `{orderId, entitlementId, status:"completed"}`
immediately. With a tip or donation it becomes flow 2 from the Stripe step onward and needs
`expectedPlatformFeePolicyVersion`. `alreadyOwned:true` is a success replay.

**4. Download a purchased file.** `GET /api/market/library` for `entitlementId` ->
`GET /api/market/products/{productId}/catalog/files?buyerScoped=true&entitlementId=...`
(`object_key` comes back `""`; that is expected, the bytes never travel this way) ->
`POST /api/storage/files/download/init` -> plain unauthenticated GET of the presigned URL
within 2 minutes.

**5. Install a purchased extension.** Once per user:
`GET /api/market/extensions/repository-credential` (or `PUT` when it is `null` or
`replacementRequired`), configure Blender with `repositoryUrl` and `accessToken`. Blender
then handles the repository index and archive download itself. For a web-initiated install:
`POST /api/market/extensions/repo/preflight {subjectType:"user", productId, versionId}`,
act on `reason` and `actions`, then `POST /api/market/extensions/drag-link` and hand
`dragUrl` to Blender. A `409` with `data.code == "repository_setup_required"` from
drag-link means the credential step was skipped.

**6. Use purchased Blender assets.** `GET /api/market/assets/library-credential` (or `PUT`
to create or rotate) -> the human pastes `libraryUrl` into Blender as a remote asset
library. Blender follows the capability-scoped metadata, index, page, preview, and file
URLs returned by the API. New purchases appear after the 10 minute snapshot refresh.

**7. Review a purchase.** Confirm ownership via `GET /api/market/library?productId=...` ->
`POST /api/market/products/{id}/reviews` (on `409` "multiple license subjects", resend with
an explicit `subjectType`/`orgId`) -> edit with `PATCH`, remove with `DELETE`.

**8. Support or refund request.** `POST /api/market/conversations {productId}` ->
`POST /api/market/conversations/{id}/messages` -> poll the thread and `POST .../read`
after rendering. The seller or a platform admin performs the refund; the buyer watches the
order status in `GET /api/market/purchases`.

---

## Collections a buyer can read directly

Use the Sulu records API only for the three collections below. Use the
documented `/api/market/*` routes for every other marketplace workflow.

| Collection | Access | Notes |
| --- | --- | --- |
| `market_categories` | Public read | Category tree for browse filters: `name`, `slug`, `icon`, `parent`, `order`. |
| `reviews` | Published public read | Includes `seller_response`, `seller_response_at`, `helpful_count`, `subject_type`, `subject_id`. |
| `wishlists` | Signed-in user's own rows | Supports list, view, create, and delete; update is unavailable. |

For products, orders, entitlements, conversations, messages, and delivery,
use `/api/market/browse`, `/api/market/products/{id}`, `/api/market/library`,
`/api/market/purchases`, and `/api/market/conversations/*` instead.

### Wishlist record operations

The `wishlists` schema contains required `user` and `product` relations plus timestamps.
A unique uniqueness constraint on `(user, product)` prevents duplicates.

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/api/collections/wishlists/records` | Lists only rows whose `user` is the authenticated user |
| `GET` | `/api/collections/wishlists/records/{id}` | Views one owned row; another user's ID is not readable |
| `POST` | `/api/collections/wishlists/records` | Creates only when body `user` equals the authenticated ID |
| `DELETE` | `/api/collections/wishlists/records/{id}` | Deletes only an owned row |

There is no user update permission. Send `{"user":"<self-id>","product":"<product-id>"}`
on create. Use exact filters and `fields=id,product,created,updated`; do not rely on record
expansion to bypass locked raw product rules. Resolve product names and publication state
through `GET /api/market/products/{id}`.

For removal, filter with the exact product:

```text
filter=(product='prod_abc123')
```

Delete the single returned wishlist record ID. An empty result is already-removed success;
multiple results indicate an integrity problem and must not be bulk-deleted.

---

## Gotchas

- **Money movers**: `POST /api/market/stripe/checkout`, and `checkout-free` with a tip or
  donation, create real Stripe sessions. `checkout-free` without a tip moves no money but
  still creates an order, an entitlement, and a ledger row: it is a real purchase, not a
  dry run.
- **Destructive without spending money**: `DELETE /api/market/reviews/{id}` (the review and
  its votes, unrecoverable), `PUT /api/market/extensions/repository-credential` and
  `PUT /api/market/assets/library-credential` (each revokes every previous credential of its
  kind for that user, breaking Blender setups on their other machines). Confirm all three
  with the human first.
- **Mutating reads**: `POST /api/market/products/{id}/view` writes a `product_views` row and
  bumps `total_views`, and `POST /api/storage/files/download/init` writes a `downloads`
  audit row, bumps `products.total_downloads`, and stamps the entitlement. Neither is safe
  to poll or to call speculatively while exploring.
- **Two 503 service gates**: the payments kill-switch
  (`503 {code:"market_stripe_payments_disabled", retryable:true}`) and the identity/cash
  freeze (`503 {code:"market_identity_cash_repair_required", retryable:true}`, which also
  covers `verify-session`, `cancel-checkout`, and `refund`). Handle both by telling the
  human, not by retrying in a loop.
- **Checkout has two required fields that are easy to miss**:
  `expectedPlatformFeePolicyVersion` (a `400` when absent, so
  `GET /api/market/platform-fee-policy` is a mandatory prerequisite) and `idempotencyKey`
  (8 to 200 visible ASCII; absent it surfaces as a `500` on `checkout` and a `409` on
  `checkout-free`, never as a clear validation error).
- **Idempotency keys are cart-bound.** Any changed field (tier, discount, tip, org) with a
  reused key is `409`. Generate a fresh key per distinct cart; reuse only to resume the
  identical attempt. Intents expire after 45 minutes.
- **Checkout responses are a union.** Branch on the keys, not the status: a `clientSecret`
  means mount Stripe, an `orderId` plus `entitlementId` means the order already exists
  (a discount zeroed the price, or this is a free claim).
- **Body strictness is inconsistent.** Strict (unknown, duplicate, or trailing fields are
  `400`): `/api/market/discount/validate`, every review body, every conversation body,
  `/api/market/extensions/drag-link`. Lenient (unknown fields silently dropped): `checkout`,
  `checkout-free`, `verify-session`, `cancel-checkout`, `refund`, `repo/preflight`. On the
  lenient routes a misspelled field name reads as an omitted value.
- **`alreadyOwned:true` is success**, not an error: fetch the library.
- **Self-purchase is blocked** for owners and members of the seller org, and for buying as
  the seller org (`400`).
- **Org licenses**: pass `buyerOrgId` at checkout; the entitlement subject becomes the org,
  delivery rechecks membership live, and org purchase *history* additionally needs a
  finance or admin role. A removed member loses repo, library, and download access at once.
- **Buyers cannot refund themselves.** `POST /api/market/refund` is `403` for buyers. Route
  requests through conversations, within 30 days of `paid_at`.
- **Bearer secrets**: `mrt_...` repo tokens are revealed on GET and PUT of
  `/repository-credential`, and `PUT` revokes all of that user's previous repo credentials.
  The asset-library `libraryUrl` **contains** its credential. Never log, print, or share
  either; rotating invalidates the old one.
- **Rate limits**: conversation messages 20/min/conversation; asset-library meta 60/min
  (`Retry-After: 60`); credential issuance hourly (`Retry-After: 3600`).
- **Reviews need proof**: *creation* requires an active entitlement whose linked order is
  `completed` or `partially_refunded` (an entitlement with no order, an explicit
  administrative grant, also counts). *Editing and deleting* recheck the same linkage with
  `requireActive = false`, so a later refund or revocation does not lock the author out;
  what does is losing membership of the review's organization (`403` "you are no longer a
  member of the review organization"). Strict JSON: unknown fields are `400`, not ignored.
- **`PATCH` on a review replaces all three fields.** Sending only `rating` blanks the title
  and body. There is no partial update.
- **Downloads**: presigned URLs live 2 minutes, so request them right before use.
  Extension and asset streams verify SHA-256 and recheck authority every second; a
  mid-stream abort means the entitlement or publication changed.
- **Caps**: browse `search` 200 chars; purchases and legacy `search` 120 chars; `perPage`
  100 everywhere; catalog `ids` 100; my-votes 100 ids; repository index 500 entries.
- **Sort values are strict** on `/browse`: an unknown value is `500`, not a fallback.
- **`/api/market/purchases` is offset-paginated over mutable data**; the library is
  cursor-paginated and stable. Prefer the library for ownership.
- **Products can disappear**: seller de-verification, suspension, or a tombstone removes a
  product from every public read (`404`) while existing entitlements generally keep
  delivering. Explicit distribution suspension or quarantine blocks delivery with a reason
  surfaced in the repository `blocklist`.
- **Never reconstruct URLs**: archive, repository, and asset URLs may use a
  different canonical origin from the API base. Use exactly what the API
  returned.
