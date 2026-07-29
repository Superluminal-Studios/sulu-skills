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
| `sulu-api` | Authentication, shared request rules, account security, organizations, projects, billing, referrals, and support |
| `sulu-render` | Approval-bound render submission, cost estimation, monitoring, editing, duplication, and results |
| `sulu-storage` | Project storage access, output layout, and marketplace transfer sessions |
| `sulu-production` | Production configuration, elements, tasks, revisions, review media, time, notifications, and planning |
| `sulu-market` | Buying, delivery, reviews, seller onboarding, products, media, discounts, orders, and earnings |

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
