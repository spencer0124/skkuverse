---
title: Web Surfaces in a Dedicated Repository
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-07
audience: public
---

# ADR 0005 — Web surfaces in a dedicated repository

> Every browser surface moves out of the React Native monorepo into `skkuverse-web`, because
> what the web app shares with the native one is a message contract rather than a component
> library.

## Status

accepted

## Context

`skkuverse-app` is a Yarn workspaces monorepo holding the React Native app and, alongside it,
a Vite single-page application for the pages the app loads in a web view.

The reason to keep two applications in one repository is the code they share. Between the
native app and the web app that comes to a single package, `packages/bridge`, which carries
the web-to-native message types and has no dependencies. Nothing else crosses, and the reason is structural
rather than incidental:

- `packages/sds` is a React Native component library. Its `peerDependencies` name only React
  Native packages, and its components import `react-native` directly. A browser cannot render
  them.
- `packages/shared` constructs its MMKV-backed storage at module load, so its entry point
  throws in a browser before any consumer sees it. The parts a browser could use, including
  the design tokens, sit behind that entry point.

Meanwhile the layout charges rent on every web build:

- The workspace root declares Expo and React Native as dependencies, so any install in that
  workspace fetches the native toolchain. Yarn 1 resolves at the workspace root, so a hosting
  provider's *root directory* setting does not narrow what gets installed.
- The root pins an exact React version for React Native, which makes React Native the
  decider of the web app's React version.
- The repo has no task runner, and its lint script is the Expo linter, so the web app has
  never been linted, type-checked or built by CI at all.
- The mobile release scripts abort on a dirty working tree, so web work in the same checkout
  blocks a mobile release.

There is also a fact that reframes the whole question: the deployed web view is served from a
separate repository, `SKKUBUS_webview`, and the copy inside the monorepo has never been the
artifact anyone runs.

## Decision

**A dedicated public repository, `skkuverse-web`, owns every browser surface. What crosses the
boundary between it and `skkuverse-app` is data, never components.**

| Concern | Owner | Rule |
| --- | --- | --- |
| Public web view pages | `skkuverse-web` | The artifact the mobile app loads. Replaces `SKKUBUS_webview` |
| Admin console | `skkuverse-web` | Identity model in [ADR 0006](0006-console-identity.md) |
| Web components | `skkuverse-web` | Written for the browser, parallel to the native design system |
| Native design system | `skkuverse-app` | Never crosses. Its dependencies are the reason |
| **Design token values** | `skkuverse-app` | Vendored into `skkuverse-web`, registered as a contract |
| **Message contract** | `skkuverse-app` | Vendored into `skkuverse-web`, registered as a contract |
| Console API and its data | `skkuverse-server` | The ad and mini-app records already live there |
| Web view origin allowlist | `skkuverse-server` | Served to the app at runtime, per [app ADR 0006](https://github.com/spencer0124/skkuverse-app/blob/main/docs/decisions/0006-miniapp-webview-push-architecture.md) |
| Hosting | Cloudflare Pages | Both surfaces are static, so neither needs a server of its own |

The invariants both repos hold:

1. **Components do not cross the boundary. Token values do.** The design language is portable
   because it is data. The rendering layer is bound to a platform toolkit and stays where
   that toolkit lives. One token source with a component set per platform is the supported
   shape, and a shared component set is not.
2. **A vendored file has one upstream owner and travels by the contract system.** Anything
   `skkuverse-web` copies from `skkuverse-app` is registered in `contracts/manifest.json`,
   hash-locked per consumer and checked offline in CI, by the mechanism in
   [ADR 0002](0002-pull-based-config-contracts.md). Registration happens when the copy is
   made. Deferring it until the file starts changing means noticing drift at the moment it
   has already reached production.
3. **Web view routes are append-only.** The mobile app embeds hardcoded web view URLs in
   released binaries, and an installed build cannot be corrected. Adding a route is safe.
   Renaming or removing one breaks clients that are already in the field.
4. **A new origin grants no capability until the server says so.** Web view capabilities are
   resolved per message against a server-owned exact-origin allowlist that fails closed.
   Preview deployments cannot exercise the bridge, so a fixed staging origin is registered in
   that allowlist rather than a wildcard.

## Consequences

- ✅ A web build installs its own dependencies rather than the native toolchain, and the web
  React version is chosen by the web app.
- ✅ The web surfaces gain lint, type-check and build gates, which the monorepo never applied
  to them.
- ✅ Mobile releases and web development stop sharing a working tree, so the dirty-tree abort
  in the release scripts no longer fires for unrelated work.
- ✅ The deployed web view becomes an artifact built from a repository that is actually
  deployed, closing the gap where the maintained copy and the running copy were different
  code.
- ⚠️ Token and message-contract changes now cross a repo boundary and land as two changes
  instead of one. This is the cost the contract system exists to bound, and invariant 2 is
  what keeps it bounded rather than silent.
- ⚠️ A change spanning both repos needs two pull requests, with the consumer merging second.
- ⚠️ The fleet gains a repository, and with it another CI configuration and another set of
  conventions to keep aligned. The umbrella's shared checks are cloned rather than vendored,
  which is what keeps that cost to a workflow file.

## Related

- Build plan: [skkuverse#22](https://github.com/spencer0124/skkuverse/issues/22)
- Console identity: [ADR 0006](0006-console-identity.md), built in [skkuverse#23](https://github.com/spencer0124/skkuverse/issues/23)
- Vendoring mechanism: [ADR 0002](0002-pull-based-config-contracts.md), [`../../contracts/manifest.json`](../../contracts/manifest.json)
- Web view trust boundary: [app ADR 0006](https://github.com/spencer0124/skkuverse-app/blob/main/docs/decisions/0006-miniapp-webview-push-architecture.md)
- Repository: [skkuverse-web](https://github.com/spencer0124/skkuverse-web)
