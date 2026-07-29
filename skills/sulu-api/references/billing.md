# Sulu billing reference

Complete endpoint reference for Sulu billing: balance, credit purchases, payment
history, automatic top-up, render pricing, referrals.

Base URL: `https://api.superlumin.al`. Auth header on every authenticated call:
`Authorization: <token>` (raw Sulu JWT from
[Sulu API guide](../SKILL.md); a `Bearer` prefix is tolerated).

**Response envelope.** The `/api/stripe/*` and `/api/referral/*` endpoints return
**bare JSON objects**, not the `{"status":"success","body":{...}}` envelope used by
some other Sulu custom routes. Their errors are Sulu-style
`{"status": <code>, "message": "...", "data": {}}`. The render pricing endpoint uses
the render contract error body instead:
`{"error":{"code","message","request_id","retryable"}}`.

**Ownership.** Every `/api/stripe/*` endpoint runs `requireOrgOwnerByID`: `401` if
unauthenticated, `403` unless the caller's user id equals `organizations.owner_id`.
There is no role-based path here, so an org member with the `admin` role is still
rejected. `/api/referral/*` needs any authenticated user.

**Money model.** 1 credit = $1.00 USD (`pricePerCreditCents = 100`).
`organizations.balance` is a float in dollars. Credits appear after payment
confirmation. Render costs are debited while work runs, so the balance can go
negative.

---

## Contents

- [Balance](#balance)
- [Credit purchases](#credit-purchases)
- [Automatic top-up](#automatic-top-up)
- [Render pricing](#render-pricing)
- [Referrals](#referrals)
- [Flows](#flows)
- [Collections behind these endpoints](#collections-behind-these-endpoints)
- [Gotchas](#gotchas)

## Balance

### GET /api/organizations/{orgId}

- **Auth**: any active member of the org (owner or member). Not owner-only.
- **Purpose**: the supported user-facing read of the credit balance.
- **Response 200** (`organizationDetailDTO`):

  | field | type | notes |
  | --- | --- | --- |
  | `id`, `name`, `description`, `color`, `avatar` | string | summary fields |
  | `owner_id` | string | user id of the owner |
  | `role` | string | caller's resolved role, omitted when absent |
  | `is_owner` | bool | whether the caller is the owner |
  | `balance` | float | **credits, in dollars**. Visible to all members. |
  | `max_node_count` | int | owner or `admin` role only |
  | `pricing_tier_id` | string | owner or `admin` role only |
  | `has_customer` | bool | owner or `admin` role only: a Stripe customer exists |

  `customer_id` and other server authority fields are never serialized.
- **Errors**: `400 organization id is invalid`; `404 organization not found` (also
  for archived or quarantined orgs); `403 not a member of this organization`.
- **Side effects**: none. Full documentation:
  [organizations and projects reference](organizations.md).

### blocked_funds (derived job status, no endpoint)

Render job DTOs are decorated at read time with `effective_status` and, when
non-empty, `status_reason`. `jobsEffectiveStatusFromCounts` returns
`effective_status: "blocked_funds"` and `status_reason: "low_funds"` when **all** of:

- the org balance is `<= 0`,
- the job's stored status is `running` or `queued`,
- no tasks are currently running,
- unfinished tasks remain.

Job DTOs also carry `org_balance` (float dollars) when the org record had a balance
field, which makes job polling a second way to watch the balance. Nothing is stored:
top up and the derived status clears on the next read. See
[render reference](../../sulu-render/reference.md).

---

## Credit purchases

### POST /api/stripe/create-checkout-session

**Spends money.** Requires the human's explicit approval of the exact credit amount
before you call it.

- **Auth**: user token, then **org owner only**.
- **Purpose**: create an embedded Stripe Checkout Session to buy render credits.
- **Required header**: `Idempotency-Key`, 8 to 200 characters drawn from
  `[A-Za-z0-9_:\-.]`. Missing or malformed gives `400`. The server hashes it into the
  Stripe idempotency key `sulu:credits:<orgId>:g<generation>:<sha256-prefix>`, so
  retrying with the same value deterministically replays the same session.
- **Body** (`createSessionReq`):

  | field | type | required | notes |
  | --- | --- | --- | --- |
  | `organizationId` | string | yes | |
  | `amount` | int64 | yes | whole credits, must be `> 0`. No server-side maximum in this endpoint (Stripe and price limits still apply). |
  | `supersedesSessionId` | string | no | a previously issued open checkout session to expire, best effort, only if it belongs to this org and is still `open` |

- **Response 200** (`Cache-Control: no-store`):
  `{"clientSecret": "<embedded checkout client secret>", "sessionId": "cs_..."}`.
  **There is no hosted payment URL.** The session is created with UI mode `embedded`,
  so completing it requires a page that mounts embedded Checkout.
- **Errors**: `400` bad JSON, missing `organizationId`, `amount must be > 0`, or an
  invalid `Idempotency-Key` (`Idempotency-Key is required`, `... must contain 8 to
  200 characters`, `... contains unsupported characters`); `404 organization not
  found` / `owner user not found`; `401`/`403` not the owner; `500 unable to prepare
  saved payment method`, `500 unable to create checkout session`, `500 unable to bind
  checkout session`.
- **Retry rule**: `500 unable to bind checkout session` is retryable **with the same
  Idempotency-Key**. The endpoint deliberately leaves the session unexpired so the
  replay can rebind it. A fresh key can strand the session.
- **Side effects**: creates a Stripe Checkout Session (`mode=payment`, automatic tax
  enabled, promotion codes allowed, saved-payment-method option enabled, metadata
  `organizationId`). If the org has no `customer_id`, the session is created with
  `CustomerCreation=always` plus the owner's email. If auto top-up is waiting for a
  card (`pending_payment_method`, `requires_action`, or `failed`), this session is
  additionally bound as the auto top-up **setup** session: forced onto the org's
  Stripe customer with `setup_future_usage=off_session` and metadata
  `autoTopUpSettingsId` + `autoTopUpSetupGeneration`. May expire superseded open
  sessions. **No credits are granted by this call**: charging and crediting
  happen only after the human pays and payment is confirmed.

### GET /api/stripe/invoices

- **Auth**: user token, org owner only.
- **Purpose**: Sulu credit top-up payment history.
- **Query**:

  | param | type | required | notes |
  | --- | --- | --- | --- |
  | `organizationId` | string | yes | |
  | `limit` | int | no | default 10, clamped to 1 to 50 |

- **Response 200**: `{"invoices": [...]}`, ordered newest-first by `stripe_created`.
  Each item:

  | field | type | notes |
  | --- | --- | --- |
  | `id` | string | first non-empty of charge id, payment intent id, checkout session id, or the record id |
  | `amount_paid` | int | **net cents** (amount minus refunds) |
  | `currency` | string | e.g. `usd` |
  | `status` | string | `paid`, `partially_refunded`, `refunded` |
  | `created` | int | unix seconds |
  | `hosted_invoice_url` | string | receipt URL, else hosted invoice URL; omitted when empty |
  | `invoice_pdf` | string | omitted when empty |

- **Errors**: `400 missing organizationId`; `404 organization not found`; `401`/`403`
  not the owner; `500` on list failure.
- **Side effects**: none, read-only, `no-store`. Refund status can lag the
  payment provider.

### POST /api/stripe/customer-portal

**Has a permanent side effect.** Confirm with the human first.

- **Auth**: user token, org owner only.
- **Purpose**: mint a Stripe Billing Portal session URL so the human can manage cards
  and see Stripe-side billing.
- **Body**: `{"organizationId": "org_abc123"}`.
- **Response 200**: `{"url": "https://billing.stripe.com/..."}` (`no-store`). Hand it
  to the human. Never open, fill, or store it.
- **Errors**: `400` bad JSON or missing `organizationId`; `404 organization not
  found`; `401`/`403` not the owner; `500 ensure customer: ...` or portal-session
  creation failure.
- **Side effects**: if the org has no Stripe customer (or a stale/deleted one), this
  **creates a Stripe Customer** (idempotency key `sulu:billing-customer:<orgId>:v1`)
  and persists `organizations.customer_id`. That is irreversible from the API and it
  permanently blocks `POST /api/referral/claim` for the owner.

---

## Automatic top-up

Once automatic top-up is active and armed, Sulu checks the balance against the
configured threshold and initiates an off-session reload plus applicable tax.
The organization receives credits after payment confirmation.

### GET /api/stripe/auto-topup

- **Auth**: user token, org owner only.
- **Query**: `organizationId` (required).
- **Response 200** (`autoTopUpResponse`):

  | field | type | notes |
  | --- | --- | --- |
  | `organizationId` | string | |
  | `enabled` | bool | |
  | `thresholdCents` | int64 | charge when the balance falls below this |
  | `reloadAmountCents` | int64 | amount purchased per automatic charge, before tax |
  | `currency` | string | always `usd` |
  | `status` | string | `disabled`, `pending_payment_method`, `active`, `requires_action`, `failed` |
  | `paymentMethod` | object or null | `{"type","brand","last4","expMonth","expYear"}`; `brand`/`expMonth`/`expYear` for cards, bank name in `brand` for `us_bank_account` |
  | `setupGeneration` | int64 | bumped by every PUT; invalidates in-flight setup sessions |
  | `lastError` | string | omitted when empty |

  When no settings record exists the defaults are returned: `thresholdCents: 1000`
  ($10), `reloadAmountCents: 5000` ($50), `status: "disabled"`.
- **Errors**: `400 missing organizationId`; `404 organization not found`; `401`/`403`
  not the owner; `500` settings unavailable.
- **Side effects**: normally none, but it **fails closed on ownership change**: if the
  stored `consent_actor` is no longer the current owner, the endpoint disables the
  setting in the service data and reports `lastError: "The current organization owner must
  authorize automatic top-ups."`. If an attempt is parked in `manual_review`,
  `status` shows `failed` and `lastError` says so.

### PUT /api/stripe/auto-topup

**Spends money.** This is the consent record for automatic charges, and when the
setting is already active with a balance under the threshold an off-session card
charge can follow **within seconds**. Requires explicit human approval of the
threshold and reload amount.

- **Auth**: user token, org owner only. The org must also be eligible: it must have an
  owner, must not be `archived`, and must not be `ownership_state =
  quarantined_ownerless`, else `409`.
- **Body** (`updateAutoTopUpRequest`):

  | field | type | required | validation |
  | --- | --- | --- | --- |
  | `organizationId` | string | yes | |
  | `enabled` | bool | yes | |
  | `thresholdCents` | int64 | yes | 100 to 1,000,000 ($1 to $10,000) **and** `% 100 == 0` (whole dollars) |
  | `reloadAmountCents` | int64 | yes | 500 to 1,000,000 ($5 to $10,000) **and** `% 100 == 0` (whole credits) |

  Both amounts are validated even when `enabled` is `false`, so a disable call must
  still carry valid values.
- **Response 200**: the same `autoTopUpResponse` shape as the GET. Enabling with no
  saved payment method returns `status: "pending_payment_method"` with
  `setupGeneration` incremented.
- **Errors**: `400` validation messages (`thresholdCents must be between 100 and
  1000000`, `thresholdCents must be a whole-dollar amount`, `reloadAmountCents must be
  between 500 and 1000000`, `reloadAmountCents must purchase a whole number of
  credits`, `missing organizationId`); `404 organization not found`; `401`/`403` not
  the owner; `409 organization is not eligible for auto top-up`; `409 an automatic
  top-up payment result needs manual review`; `500` save failure.
- **Side effects**: records consent (`consent_actor` = caller, `consent_version`
  currently `2026-07-28`). Every PUT bumps `setup_generation`, which invalidates any
  in-flight setup checkout session. If the setting was already fully active and stays
  enabled, it re-arms and immediately schedules a worker scan, which is where the
  within-seconds charge comes from. Disabling clears status, armed flag, last error,
  and the pending setup session; the stored Stripe payment method id is kept on the
  record but reported as disabled, and re-enabling from a non-active status clears the
  stored method fields so a new checkout is needed to capture a card.
- **`manual_review`**: an ambiguous Stripe outcome parks the attempt for a human
  operator. It blocks re-enabling and new setup until resolved. Do not retry: tell the
  user to contact Sulu support.

---

## Render pricing

Authenticated organization members use
`GET /api/render/capacity/{organization_id}` and its
  `effective_rate_table_microusd`, `effective_rate_microusd`, `rate_basis_gpus`,
  `curve_version_id`, `curve_checksum`, and `multiplier_bps` fields. See
  [render reference](../../sulu-render/reference.md).
- **Estimation rule**: combine the returned concurrency and rate with a conservative
  runtime assumption or relevant completed-job evidence and contingency, then recheck
  immediately before submission.

---

## Referrals

### POST /api/referral/generate

- **Auth**: any authenticated user. Not org-scoped.
- **Body**: none.
- **Response 200**: `{"code": "J7K2P5QX"}`, an 8-character string drawn from the
  alphabet `A-Z` plus `2-7` (the digits `0`, `1`, `8`, `9` never appear).
  Idempotent: returns the existing code when the user already has one.
- **Errors**: `401 auth required`; `500` on storage failure.
- **Side effects**: the first call creates a `referrals` record with the default
  reward schedule: the referrer gets **10% of each purchase** by the referred user
  (`percentage_from = 10`, unlimited uses), the referred friend gets a one-time
  **$10** (`amount_to = 10`, `max_to_usages = 1`).

### POST /api/referral/claim

**One-shot and permanent.** A user can claim exactly one code, ever, and cannot
change it. Confirm the code with the human before sending.

- **Auth**: any authenticated user.
- **Body**: `{"code": "R3TW6MB4"}` (someone else's code). Trimmed and uppercased
  server-side.
- **Response 200**: `{"status": "claimed"}`.
- **Errors**: `400` bad JSON, empty code, `you have already claimed a referral code`,
  `cannot use your own code`, or `referrals unavailable after first purchase`;
  `404 code not found`; `401 auth required`.
- **Side effects**: creates a `referral_usages` row with `usages = 0`,
  `earnings = 0`. **No credits move at claim time.** On each later qualifying
  purchase confirmation credits the friend bonus ($10, once) to the buyer's owned org
  and the referrer bonus (10% of purchased credits, uncapped uses) to the referrer's
  owned org. Each bonus lands on the first organization that user owns, which for a
  multi-org account is not necessarily the organization that made the purchase.
- **Eligibility trap**: the block fires once the claimer's owned org has any Stripe
  `customer_id`, which is set by the first checkout **or** by opening the customer
  portal, not strictly by the first payment. Claim before touching either.
- No `/api/referral/*` route reports referral earnings or usage counts. Bonuses are
  visible only as a balance increase.

---

## Flows

### Buy credits (manual top-up)

1. Confirm the exact credit amount and dollar total with the human.
2. Generate an idempotency string (8 to 200 chars, `[A-Za-z0-9_:\-.]`) and keep it
   for retries.
3. `POST /api/stripe/create-checkout-session` with the `Idempotency-Key` header and
   `{"organizationId", "amount"}` gives `{clientSecret, sessionId}`.
4. A frontend mounts Stripe Embedded Checkout with `clientSecret` and the human pays.
   Card payments complete without a redirect (`redirect_on_completion=if_required`);
   the return URL contains `{CHECKOUT_SESSION_ID}`. **An agent with no such frontend
   should skip steps 2 and 3 entirely and send the human to the Sulu web app billing
   page (`https://superlumin.al/billing`).**
5. After payment confirmation, Sulu records the payment, adds credits to the
   organization balance, and applies any referral bonus. Some payment methods
   settle asynchronously.
6. Poll `GET /api/organizations/{orgId}` for the new balance, or
   `GET /api/stripe/invoices` for the receipt, at 10 seconds or slower. There is no
   user-facing "check checkout session status" endpoint.
7. If the human abandons and re-opens checkout, reuse the same `Idempotency-Key` or
   pass the old id as `supersedesSessionId` so the stale session is expired.

### Enable auto top-up with no card on file

1. `GET /api/stripe/auto-topup?organizationId=...` shows `status: "disabled"` with
   defaults ($10 threshold, $50 reload).
2. Confirm the threshold and reload amount with the human, then
   `PUT /api/stripe/auto-topup` with `{"organizationId", "enabled": true,
   "thresholdCents", "reloadAmountCents"}`. Response is
   `status: "pending_payment_method"`.
3. Run the buy-credits flow. Because the setting needs a payment method, that
   checkout session doubles as the card-capture session and saves the card for
   off-session reuse (the human sees this in Stripe's UI).
4. On payment confirmation the setting activates: `status: "active"` and
   `paymentMethod` is populated. Re-read the GET to confirm.
5. From then on the worker charges the saved card automatically whenever the balance
   falls below the threshold. Failures surface as `status: "requires_action"` or
   `"failed"` with `lastError`; a parked attempt reports the manual-review message
   and blocks further attempts until an operator resolves it.

### Disable auto top-up

`PUT /api/stripe/auto-topup` with `"enabled": false` and still-valid threshold and
reload values. Response `status: "disabled"`. Bumps `setupGeneration`, killing any
in-flight setup session.

### Manage cards or see Stripe-side billing

`POST /api/stripe/customer-portal` with `{"organizationId"}`, then hand the returned
`url` to the human. Remember it can create a Stripe customer.

### Referral

1. Referrer: `POST /api/referral/generate`, share the `code`.
2. New user, before any purchase or portal visit: `POST /api/referral/claim`.
3. Bonuses land automatically on later purchases, visible only as balance increases.

---

## Collections behind these endpoints

Use the documented billing routes for all billing and referral operations.
The organization owner may read their `payments` records, but must never create,
update, or delete them through the generic records API. Do not query or modify
referral records directly; use `/api/referral/*`.

Payment records can include status, amounts, purchased credits, receipt and
invoice links, timestamps, and payment metadata. Treat all of it as private
financial information.

---

## Gotchas

- **Nothing is credited synchronously.** Checkout creation, portal creation, and
  referral claims move no money. Poll balance or invoices instead of assuming.
- **Owner-only, not member.** All `/api/stripe/*` calls reject non-owner members with
  `403`, including members with the `admin` role. Treat `403` as a boundary: report it
  and stop, do not try other ids.
- **`Idempotency-Key` is mandatory** on checkout creation, and `500 unable to bind
  checkout session` must be retried with the **same** key.
- **`PUT /api/stripe/auto-topup` can cause a real card charge within seconds.**
- **Balance can go negative**: debits have no floor.
- **Ownership change invalidates auto top-up consent** automatically, and the previous
  owner's card summary is never disclosed to the new owner.
- **`GET /api/stripe/invoices` is the local ledger**, not live Stripe.
- **Default public pricing may be unavailable.** Use the
  authenticated capacity response for an org-specific estimate and recheck before
  submission.
- **Referral claiming is blocked by a Stripe customer existing**, which the customer
  portal creates.
