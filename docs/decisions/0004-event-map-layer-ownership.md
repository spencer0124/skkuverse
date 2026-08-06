---
title: Event Map Layer Ownership Across Repos
type: adr
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-06
audience: public
---

# ADR 0004 — Event map layer ownership

> A temporary event map spans four repos: content and contracts on the server, rendering in the app,
> pages in the webview, delivery in the functions. This is the cross-repo contract for who decides
> what. Implementation lives in [skkuverse#11](https://github.com/spencer0124/skkuverse/issues/11).

## Status

accepted

## Context

An event map is drawn from data that changes during the event itself, on a day when a store release
is impossible. Which layers exist, what is open, what a chip means — all of it must be answerable
without shipping a build.

The harder question is not *where the data lives* but *what the map is allowed to know*. A map that
knows about "the festival" is a map that must be rewritten for the next event. So the boundary this
ADR draws is less about storage than about vocabulary.

## Decision

**The server owns every decision; the app owns only how to draw one. Config is split by who edits
it, not by what it is.**

| Concern | Owner | Rule |
| --- | --- | --- |
| Layer / chip / filter **structure** | server repo, validated JSON | Schema, not content. Validated at materialization; invalid config is never published |
| **Activation** window + `enabled` | server, **Mongo** | Rain delays and early closes are content events. A deploy on festival night is itself the risk |
| **Content** (places, sessions) | server, **Mongo** | Operationally editable, zero code coupling |
| Status, tags, i18n resolution, icon URLs | server, at materialization | The app never derives, never translates, never branches on category |
| **Action vocabulary** on sheet buttons | server picks per button, app renders | `content` · `route` · `webview` · `external` · `miniapp`. The extension point (§1 below) |
| Marker drawing, predicate evaluation, distance | app | The only client computation, and none of it is a business rule |
| Non-map content | **webview** (`apps/webview`) | Pages, not native screens |
| Push topic selection | **functions, forced server-side** | The caller names a mini-app, never a topic |

Four cross-repo invariants:

1. **The map is a reusable place renderer, and extension happens through actions.** The map knows
   about *places* — a building and a booth are the same kind of thing, addressed the same way, and
   opened by the same universal scheme `skkuverse://map?place=<placeId>`. It must never learn the
   name of a consumer. Everything event-specific sits behind one indirection, the action union on
   sheet buttons, so next year's event changes the payload and nothing else.
2. **Fail loud where you can fix it, fail soft where you can only render it.** The server refuses to
   publish an invalid config and keeps the previous snapshot live; the client drops what it does not
   understand and renders the rest. Unknown predicate nodes evaluate `false` — hiding an item is
   recoverable, revealing a hidden one is not.
3. **Coordinates convert in exactly one place.** Mongo and GeoJSON are `[lng, lat]`; the app's
   `PolylineCoord` is `[lat, lng]`. The wire carries **named `lat`/`lng` fields and no positional
   tuples**, and the server is the only converter. A swap is silent and lands in the ocean.
4. **Shared artifacts have one origin, propagated by the contract system.** Anything two repos must
   agree on byte-for-byte is registered in `skkuverse/contracts/manifest.json`, hash-locked per
   consumer, checked offline in CI, and refreshed by the daily sync PR. Mechanism and rationale:
   [umbrella ADR 0002 — pull-based config contracts](0002-pull-based-config-contracts.md). Do not
   hand-maintain a second copy.

## Consequences

- ✅ A festival-day fix is a one-field Mongo edit, live within ~2 minutes or immediately via silent push.
- ✅ Next year's event ships as data — the map, the place model and the sheet are unchanged.
- ✅ Always-on layers (toilets, first aid) survive the event data being deleted, and `/map/config`
  is untouched, so a failure in either map system cannot take down the other.
- ⚠️ `actionValue` must always be a complete URL — a relative string handed to a URL opener is the
  shape of an open redirect. This is the only compatibility rule that survives: the app ships over
  the air, so a client that cannot read an action type is one we update, not one the server gates.
- ⚠️ Structure lives in the server repo while activation lives in Mongo, so "the config" has two
  homes. Only obvious once you ask *who fixes this at 22:00*.
- ⚠️ Status is recomputed on-device, so a wrong device clock shows wrong hours. Bounded by a skew
  check against the server `Date` header.
- ⚠️ Mini-app push requires an inbox, contradicting
  [**app** ADR 0002 — no notification inbox](https://github.com/spencer0124/skkuverse-app/blob/main/docs/decisions/0002-no-notification-inbox.md).
  That ADR names this exact revisit condition in its own consequences — an alert that is not a
  notice has no recovery path if missed, so the decision is to be revisited once that kind of alert
  grows — which means amend it, do not silently override. The inbox adopted here is
  **broadcast-only**: no per-user state, no read/unread, no auth. Note the number collision:
  umbrella ADR 0002 is *pull-based config contracts*, invoked by invariant 4. Always qualify the repo.

## Related

- Implementation plan: [skkuverse#11](https://github.com/spencer0124/skkuverse/issues/11)
- Server: `docs/reference/eventmap-api.md` — schema, materialization, endpoints
- App: `docs/eventmap-rendering.md` — parsing, predicates, rendering
- Shared-artifact mechanism: [umbrella ADR 0002](0002-pull-based-config-contracts.md), `contracts/manifest.json`
- Mini-app trust boundary and push origination: [app ADR 0006](https://github.com/spencer0124/skkuverse-app/blob/main/docs/decisions/0006-miniapp-webview-push-architecture.md)
