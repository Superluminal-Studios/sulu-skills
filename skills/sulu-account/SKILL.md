---
name: sulu-account
description: Read and safely manage the signed-in Superluminal (Sulu) user's own profile, avatar, username, email, password, verification state, OAuth links, remembered sign-in origins, and account deletion through the user-scoped Sulu API.
---

# Sulu account API

Use this skill only for the authenticated user's own account. Load
[sulu-api](../sulu-api/SKILL.md) for authentication and shared request rules,
and follow the [shared guardrails](../../GUARDRAILS.md).

## Establish identity

Start with:

```http
POST /api/collections/users/auth-refresh
```

Use the returned user record ID as the only valid target for self-profile
reads, updates, linked identities, and deletion. Stop if the token is not a
normal users-collection token or the returned identity differs from the
expected account.

## Read the profile

```http
GET /api/collections/users/records/{selfId}
```

Request only fields needed for the task. Profile data can include email,
verification state, public display fields, preferences, avatar metadata, and
timestamps. Treat email, provider IDs, auth origins, and preference data as
private.

## Update profile fields

```http
PATCH /api/collections/users/records/{selfId}
```

For ordinary profile changes, patch only the requested fields:

- `display_name`;
- `user_name`;
- `description`;
- `emailVisibility`;
- `prefs`.

Show a before/after summary first. Do not include ID, email, password,
verification, token, role, relation, or server-maintained fields in an
ordinary profile PATCH.

### Username availability

The users list is publicly readable, but enumeration is prohibited. Check only
the exact requested username:

```http
GET /api/collections/users/records?filter=(user_name='{requestedName}')&fields=id&perPage=1
```

Return only availability. Do not expose matching profiles or try variants
without the human asking.

### Avatar

Use `multipart/form-data` to PATCH the authenticated user's record with the
documented `avatar` field. Confirm the selected image, type, size, and digest.
Do not send another user's record ID or unrelated fields.

## Authentication methods

```http
GET /api/collections/users/auth-methods
```

Use only methods the server advertises. OAuth linking and sign-in require the
human to complete the provider interaction.

### Linked OAuth identities

List only the current user's records:

```http
GET /api/collections/_externalAuths/records
```

Before unlinking:

1. Identify the provider and exact link.
2. Demonstrate another working sign-in method.
3. Obtain explicit confirmation.
4. Delete the confirmed link once.
5. Re-read the list.

```http
DELETE /api/collections/_externalAuths/records/{linkId}
```

Never unlink the last demonstrated sign-in path.

### Remembered auth origins

Read the current user's `_authOrigins` records only when diagnosing sign-in
history or provider state:

```http
GET /api/collections/_authOrigins/records
```

Treat origin data as private security information. Do not use it to infer or
probe other accounts.

## Password and email flows

### Authenticated password change

Patch the self record with the complete Sulu password-change contract:

- current `oldPassword`;
- new `password`;
- matching `passwordConfirm`.

Require the human to supply the values for this task. Never display, retain, or
reuse them.

### Password reset email

```http
POST /api/collections/users/request-password-reset
```

Send only the human-confirmed email address. The endpoint intentionally does
not reveal whether an account exists. Request once and do not use it for
discovery.

The human completes the emailed reset token through:

```http
POST /api/collections/users/confirm-password-reset
```

Do not ask the human to paste reset tokens into chat.

### Email verification

```http
POST /api/collections/users/request-verification
POST /api/collections/users/confirm-verification
```

Request verification only for the signed-in account. The human should complete
the emailed token in a protected browser flow.

### Email change

```http
POST /api/collections/users/request-email-change
POST /api/collections/users/confirm-email-change
```

Confirm the exact new address. The human completes the emailed token with the
current password. Refresh authentication afterward and verify the resulting
identity and email.

## Delete the account

Account deletion is irreversible and can cascade into organizations, projects,
storage, marketplace state, and production records.

Before:

1. Refresh and verify the self ID.
2. Inventory owned organizations and projects.
3. Explain cascade effects and export options.
4. Resolve active renders, marketplace obligations, and needed data.
5. Obtain fresh confirmation naming the account.

Then call once:

```http
DELETE /api/collections/users/records/{selfId}
```

Do not retry an ambiguous response. First determine whether the old token still
authenticates and whether the account remains visible through an authorized
read.

## Safety boundaries

- Never read, update, unlink, or delete another user's account.
- Never enumerate users from the public list rule.
- Never expose passwords, reset tokens, OAuth codes, provider IDs, or auth
  tokens.
- Never silently change email visibility, sign-in methods, or security
  settings.
- Treat deletion and unlinking as named-target, freshly confirmed actions.

## Reference

Read the [complete account endpoint reference](reference.md) for request fields,
Sulu auth behavior, multipart avatar rules, system-collection access, and
error cases.
