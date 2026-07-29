---
name: sulu-billing
description: Read and safely manage the signed-in user's Superluminal (Sulu) billing information through the API. Use for organization balance, render pricing, credit checkout, invoices, Stripe customer portal access, automatic top-up consent, payment records, and referral codes.
---

# Sulu billing API

Use [sulu-api](../sulu-api/SKILL.md) for authentication and
[sulu-organizations](../sulu-organizations/SKILL.md) to resolve an authorized
organization. Follow the [shared guardrails](../../GUARDRAILS.md).

Billing responses contain financial and payment information. Return only the
fields needed for the human's request.

## Balance and render pricing

Read organization balance:

```http
GET /api/organizations/{orgId}
```

Read the current capacity-pricing snapshot:

```http
GET /api/render/capacity/{orgId}
```

Use the returned effective rate table, GPU shape, and plausible concurrency
bound. Combine them with a conservative runtime assumption or relevant
completed-job evidence. Include contingency and state that the result is not a
server-enforced spending cap.

If a job reports `effective_status: "blocked_funds"`, tell the human the
organization needs credits. Do not resubmit the job or purchase credits
without approval.

## Credit checkout

```http
POST /api/stripe/create-checkout-session
```

This creates a Stripe Embedded Checkout session for a specific organization
and amount. It is not a hosted payment URL.

Before:

1. Read the current balance.
2. Confirm the organization and exact amount.
3. Explain that the session must be completed in a compatible frontend.
4. Obtain explicit human approval.
5. Use an idempotency key that identifies this approved checkout intent but
   contains no secret.

Treat the returned client secret as a credential. Give it only to the approved
Stripe frontend and do not display or retain it.

After the human completes payment, re-read the balance or authorized payment
records. Never infer payment success from session creation.

## Invoices

```http
GET /api/stripe/invoices?organizationId={orgId}
```

Use bounded pagination. Invoice URLs are short-lived capabilities and must not
be logged or exposed beyond the human who requested them.

## Customer portal

```http
POST /api/stripe/customer-portal
```

The request names the organization. The response contains a short-lived Stripe
portal URL. Require the human to request the portal, then hand the URL directly
to their browser without opening, filling, or retaining it.

## Automatic top-up

Read current consent:

```http
GET /api/stripe/auto-topup?organizationId={orgId}
```

This GET can repair consent state and is therefore a side-effecting read. Call
it deliberately and do not poll it.

Update:

```http
PUT /api/stripe/auto-topup
```

The body includes organization, enabled state, threshold, reload amount, and
currency. Enabling top-up can cause an off-session charge soon after the
request when balance is below the threshold.

Before enabling or changing:

1. Read current consent.
2. Show organization, threshold, reload amount, currency, and payment-method
   summary.
3. Explain the automatic-charge behavior.
4. Obtain explicit approval for those exact values.
5. Send once.
6. Re-read consent.

Disabling also requires confirmation, but should not create a charge. Never
enable top-up as a recovery action without the human asking.

## Payment records

Authorized payment records are available through:

```http
GET /api/collections/payments/records
```

Filter to the selected organization and request only needed fields. Records are
audit evidence; do not create, update, or delete them through collection CRUD.

## Referrals

Generate the signed-in user's referral code:

```http
POST /api/referral/generate
```

This returns the existing code or creates one. Call only when the user asks for
their code.

Claim a referral:

```http
POST /api/referral/claim
```

Claiming can credit accounts and is intentionally one-time. Confirm the exact
code and intended account, then call once. Never self-refer, create referral
rings, cycle accounts, or probe codes.

Referral and usage records are read-only audit data:

```http
GET /api/collections/referrals/records
GET /api/collections/referral_usages/records
```

Use only records authorized for the signed-in user.

## Safety boundaries

- Never create charges, sessions, portal links, or consent changes without a
  direct user request.
- Never expose Stripe client secrets, portal URLs, invoice URLs, or payment
  details.
- Never retry an ambiguous checkout, portal, auto-top-up, or referral write.
- Never use referrals for self-dealing, evasion, or artificial credits.
- Do not call Stripe APIs directly when the user-scoped Sulu endpoint owns the
  workflow.
- Report declined, unavailable, or authorization responses without probing.

## Reference

Read the [complete billing reference](reference.md) for request fields,
currency and amount constraints, Stripe response shapes, auto-top-up state,
payment collections, render pricing inputs, and referral behavior.
