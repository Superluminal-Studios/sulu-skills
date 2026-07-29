# sulu-skills

**Experimental.** Client-agnostic agent skills for the public Superluminal
(Sulu) API at `https://api.superlumin.al`.

Each skill contains a concise entrypoint, a detailed HTTP reference, and agent
discovery metadata. The guides describe request methods, public paths, fields,
response contracts, side effects, and approval boundaries without prescribing
a programming language, command-line tool, or local file layout.

## Skills

| Skill | Covers |
| --- | --- |
| `sulu-api` | Authentication, access tokens, request conventions, records, pagination, files, and realtime |
| `sulu-account` | Profile, avatar, username, password and email lifecycle, sign-in connections, and account deletion |
| `sulu-render` | Approval-bound render submission, cost estimation, monitoring, editing, duplication, and results |
| `sulu-storage` | Project storage access, output layout, and marketplace transfer sessions |
| `sulu-organizations` | Organizations, memberships, roles, and projects |
| `sulu-production` | Production configuration, elements, tasks, revisions, review media, time, notifications, and planning |
| `sulu-billing` | Balance, credit purchases, invoices, auto top-up, pricing, and referrals |
| `sulu-market` | Catalog browsing, wishlists, checkout, library, reviews, conversations, and delivery |
| `sulu-market-seller` | Seller onboarding, products, versions, tiers, media, wiki, discounts, orders, and earnings |
| `sulu-support` | Authenticated support conversations, messages, attachments, and presence |

The public API inventory in [api-surface.json](api-surface.json) assigns every
documented user route and collection to one skill. [API-SURFACE.md](API-SURFACE.md)
explains how that inventory is organized.

## Render submissions

The render guide walks an agent through authentication and scope checks,
storage preparation, current capacity and balance reads, conservative cost
estimation, human approval, one submission, and result reconciliation. It does
not recommend a separate validation render, use concrete local filenames, or
assume a particular API client.

## Safety

Every skill follows [GUARDRAILS.md](GUARDRAILS.md). Agents act only for the
authenticated user, stay within confirmed organization and project scope, ask
before spending money or making consequential changes, protect credentials,
and use only endpoints documented for the requested workflow.

## Validation

Run:

```text
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
```

The validator checks skill structure, discovery metadata, references, links,
placeholders, syntax, API-guide style, and complete ownership of the documented
public API inventory.
