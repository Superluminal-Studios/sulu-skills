# Sulu public API inventory

This is the human-readable companion to [api-surface.json](api-surface.json).
The inventory covers only public and authenticated-user workflows.

## Coverage

The inventory maps:

- 140 Sulu-specific public or authenticated route pairs;
- 34 user-accessible collections; and
- 19 shared authentication, record, file, and realtime route pairs.

Every entry names one owning skill. The validator confirms that the owning
skill documents the route or collection and that no two inventory sections
claim the same route.

## Ownership

| Skill | Public API domain |
| --- | --- |
| `sulu-api` | Authentication, request conventions, records, files, and realtime |
| `sulu-account` | Signed-in user profile and security lifecycle |
| `sulu-organizations` | Organizations, memberships, roles, and projects |
| `sulu-production` | Production configuration, work tracking, review, media, and planning |
| `sulu-render` | Render settings, estimates, submission, job controls, and results |
| `sulu-storage` | Project storage and marketplace transfer sessions |
| `sulu-billing` | Balance, credits, invoices, pricing, auto top-up, and referrals |
| `sulu-market` | Catalog, buyer checkout, library, delivery, reviews, and conversations |
| `sulu-market-seller` | Seller onboarding, product management, orders, and earnings |
| `sulu-support` | Authenticated support messaging |

Cross-domain workflows have one primary owner and link to the other relevant
skills. For example, storage owns byte transfer while render owns the
spend-producing submission.

## Inclusion policy

Include an operation only when it is part of a documented user workflow.
Do not inventory or describe privileged administration, operational controls,
service-to-service traffic, inbound integrations, diagnostics, or deployment
surfaces. Their absence is intentional and does not imply permission to
discover or call them.

An HTTP success response is not sufficient authorization. Agents must still
confirm the signed-in identity, organization, project, role, target, approval,
and conduct requirements described by the owning skill.

## Maintenance

When the public API changes:

1. update the owning skill and its detailed reference;
2. update the public inventory;
3. run repository validation and every changed skill's quick validator; and
4. review examples for credentials, private terminology, concrete filenames,
   and unsupported behavior.

The inventory is documentation evidence, not a substitute for runtime
authorization checks or human confirmation.
