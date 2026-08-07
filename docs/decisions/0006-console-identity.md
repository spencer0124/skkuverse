---
title: Console Identity and Authorization
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-07
audience: public
---

# ADR 0006 — Console identity and authorization

> The admin console serves external users who sign themselves up, so identity reuses the
> ecosystem's existing auth provider and every authorization decision is an explicit claim
> checked by the server.

## Status

accepted

## Context

The console in `skkuverse-web` is used by advertisers and mini-app operators from outside the
university, alongside internal notification senders. Accounts appear without an administrator
provisioning each one, and the roles differ by what the account is for.

**Zero-trust network access**, meaning Cloudflare Access in front of the hostname, is
workforce identity. It gates a roster an administrator maintains and prices per seat past a
free allowance. There is no self-service signup and no per-tenant data scoping, so onboarding
an advertiser is an administrator editing a policy, which is the work this decision exists to
avoid.

**Managed customer identity**, meaning Clerk or WorkOS, supplies organizations, invitations
and roles as product features. It also adds a second identity system beside the one the
ecosystem already runs, and on at least one of them roles beyond the built-in pair sit behind
a monthly add-on.

**The provider already in the ecosystem** is Firebase Auth, which the mobile app uses, and
whose Admin SDK is already a dependency of `skkuverse-app`'s Cloud Functions package. It has
no native organizations or roles. That gap matters less than it first appears, because the
console has no data of its own: ad and mini-app records live in MongoDB behind
`skkuverse-server`, which already owns request guards and is where scoping has to happen
regardless of who issues the token.

One property of passwordless sign-in shapes everything downstream. An email-link flow issues
an identity to any address that asks for one, so holding a valid token says only that someone
controls a mailbox. Authorization cannot be derived from the token's validity.

## Decision

**Firebase Auth email-link sign-in, in a Firebase project separate from the app's, with every
authorization decision an explicit claim that `skkuverse-server` checks.**

| Concern | Owner | Rule |
| --- | --- | --- |
| Authentication | Firebase Auth, email link | No passwords, so no storage, reset flow or breach surface |
| User pool isolation | A **separate** Firebase project | An app user's token fails on issuer and audience, without any check having to notice |
| Authorization | Custom claims on the console user | Absence of a claim is a denial |
| Enforcement point | `skkuverse-server` | Verified with the Admin SDK on every console route |
| Data scoping | `skkuverse-server`, by owner | Applied to the query, never to the rendered result |
| Console API | `skkuverse-server` | The records already live there, so a second backend would only proxy |
| Push send credential | `skkuverse-server` environment | The console calls the server; the server holds the key |

The invariants:

1. **A valid token proves identity and nothing else.** Every console route requires an
   explicit role claim, and the absence of one is a denial rather than a fallback. This is the
   whole security model, because signup is open by design.
2. **Signup is self-service. The grant is not.** Anyone may create an identity. Turning that
   identity into access is a deliberate act, which keeps open registration from being open
   access.
3. **Scoping is a server-side filter.** A request for another owner's record fails at the
   query, so the client never receives data it would have to be trusted to hide.
4. **Isolation is structural.** Console users live in their own Firebase project so that
   separation survives a mistake in the claim check, rather than depending on it.

## Consequences

- ✅ No new vendor, no per-seat pricing, and no second identity dashboard, since the provider
  and its Admin SDK are already in the fleet.
- ✅ The client-side plumbing exists. `skkuverse-app`'s API layer already takes its token
  through an injected provider precisely so it stays environment-agnostic, so the console
  registers the web SDK into that seam rather than writing an auth client.
- ✅ A mobile user's token cannot reach the console even if a guard is written wrongly,
  because it fails verification before any claim is read.
- ✅ App Check stays a mobile concern. The app attests with platform-native providers, and a
  separate project keeps the console clear of that configuration.
- ⚠️ The console's Firebase project is operated apart from the app's, carrying its own
  configuration, quota and emulator setup.
- ⚠️ Organizations and invitations are not supplied by the provider. If advertisers grow into
  teams, that becomes application data in `skkuverse-server` or a reason to revisit the
  managed option above.
- ⚠️ Invariant 1 is a property of code rather than of infrastructure, so it holds only while
  it is tested. An automated check that a valid but claimless token is refused by every
  console route is a release gate.

## Related

- Repository split and what crosses it: [ADR 0005](0005-web-surfaces-dedicated-repo.md)
- Build plan: [skkuverse#23](https://github.com/spencer0124/skkuverse/issues/23), blocked by [skkuverse#22](https://github.com/spencer0124/skkuverse/issues/22)
- Console API and guards: [skkuverse-server](https://github.com/spencer0124/skkuverse-server)
- Console app: [skkuverse-web](https://github.com/spencer0124/skkuverse-web)
