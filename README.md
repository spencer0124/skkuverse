# SKKUverse

Coordination repo for the SKKUverse ecosystem: cross-repo documentation, shared conventions, and config contracts.

[📋 Project Board](https://github.com/users/spencer0124/projects/1)

SKKUverse is a campus app for Sungkyunkwan University. Each repository below releases on
its own schedule. A Python ingest plane crawls and summarises department notices, a NestJS
serving plane reads and serves them, and the two planes meet through a single MongoDB
Atlas cluster. All of it runs on one free Oracle Cloud ARM VM.

There is no application code here. What is here gates other repositories' CI, so a bad
commit can redden several pipelines at once.

## Repositories

| Repo | Role | Plane |
| --- | --- | --- |
| [skkuverse-server] | Read API, bus information, push dispatch orchestration | serving |
| [skkuverse-crawler] | Crawls and cleans department notices and the academic calendar | ingest |
| [skkuverse-ai] | Structured summaries of notice bodies. Stateless, no database access | ingest |
| [skkuverse-app] | Mobile client. Live shuttle, notice feed, building search | client |
| [skkuverse.com] | Marketing and landing site | client |
| [skkuverse-codepush] | Self-hosted OTA update server for the app's JS bundle | infrastructure |

Issues for the whole fleet are filed here, whatever repository the change is made in, and
the board above is the view across them.
[conventions/issue-tracking.md](conventions/issue-tracking.md) covers which label,
milestone or project field carries which part of the description.

## How changes propagate

Configuration owned by one repo and vendored by another is a *contract*. Edit the
producer's copy and open a PR. Each consumer adopts the change by running
`sync_contracts.py pull`, which rewrites its lock file. Nothing is pushed across
repository boundaries.

<!-- contracts:start -->
| Contract | Owned by | Vendored into | Enforced |
| --- | --- | --- | --- |
| `bridge.message-types` | [app] `packages/bridge/src/types.ts` | [web] `packages/bridge/src/types.ts` | yes |
| `conventions.docs-template` | [umbrella] `docs/_template.md` | [server] `docs/_template.md`, [app] `docs/_template.md` | yes |
| `conventions.markdownlint` | [umbrella] `conventions/markdownlint.jsonc` | [server] `.markdownlint.jsonc`, [app] `.markdownlint.jsonc` | yes |
| `design.colors` | [app] `packages/shared/src/tokens/colors.ts` | [web] `packages/tokens/src/colors.ts` | yes |
| `design.radius` | [app] `packages/shared/src/tokens/radius.ts` | [web] `packages/tokens/src/radius.ts` | yes |
| `design.spacing` | [app] `packages/shared/src/tokens/spacing.ts` | [web] `packages/tokens/src/spacing.ts` | yes |
| `design.typography` | [app] `packages/shared/src/tokens/typography.ts` | [web] `packages/tokens/src/typography.ts` | yes |
| `notices.categories` | [crawler] `py/generated/server-categories.json` | [server] `src/notices/categories.json` | yes |
| `notices.exclude-reasons` | [crawler] `py/generated/server-exclude-reasons.json` | [server] `src/notices/exclude-reasons.json` | yes |
| `notices.sources` | [crawler] `py/generated/server-sources.json` | [server] `src/notices/sources.json` | yes |
| `notices.tab-keys` | [crawler] `py/generated/server-categories.json` | [app] `functions/src/notifications/tabsContract.generated.ts` | yes |
| `notices.topic-cap` | [app] `functions/src/notifications/tabsContract.ts` | [server] `src/notices/notices.topics.ts` | yes |
| `search.config` | [crawler] `search.json` | [ai] `app/generated/search.json`, [server] `src/notices/search.json` | not yet |
| `search.source-whitelist` | [crawler] `py/generated/ai-sources.json` | [ai] `app/generated/sources.json` | not yet |

14 contracts — 12 active, 2 planned.

[ai]: https://github.com/spencer0124/skkuverse-ai
[app]: https://github.com/spencer0124/skkuverse-app
[crawler]: https://github.com/spencer0124/skkuverse-crawler
[server]: https://github.com/spencer0124/skkuverse-server
[umbrella]: https://github.com/spencer0124/skkuverse
[web]: https://github.com/spencer0124/skkuverse-web
<!-- contracts:end -->

Each consumer pins its copy by content hash in its own `.contracts.lock.json`, and the
check comparing the two runs offline inside that repo's CI. So a red build is always
fixable in the branch that caused it. [contracts/README.md](contracts/README.md) covers
the mechanism and the day-to-day commands.

## Conventions

Rules that apply to every repository are defined once in [conventions/](conventions/) and
enforced in each repo's CI. Conventions that are files travel as contracts, in the table
above. Conventions that are properties of a repo's own files are checked by
[`exported/lint_conventions.py`](exported/lint_conventions.py), which reads only the repository
it is pointed at and needs no network.

Prose style is enforced too. The rules live in [`.vale.ini`](.vale.ini) and
[`styles/skkuverse/`](styles/skkuverse/). [conventions/prose.md](conventions/prose.md)
explains what a linter cannot judge.

`CONTRIBUTING.md` and the issue templates come from [spencer0124/.github][dotgithub],
which GitHub applies to every repository in the org that does not define its own.

## Fleet snapshot

Each repo's `main` is pinned here as a git submodule once a day and committed, which makes
this repository's history a day-by-day record of what the whole system was. The table is
generated by [`internal/render/fleet_table.py`](internal/render/fleet_table.py). Do not edit it by hand.

<!-- fleet:start -->
| Repo | Pinned `main` | Committed (KST) | Subject |
| --- | --- | --- | --- |
| skkuverse-server | [`3a7bd64`](https://github.com/spencer0124/skkuverse-server/commit/3a7bd64644dd811a6ff6340e326d083a51bc571d) | 2026-08-07 | Merge pull request #98 from spencer0124/deploy/webview-origin-grant |
| skkuverse-crawler | [`3c6c08d`](https://github.com/spencer0124/skkuverse-crawler/commit/3c6c08de969b739d43ef8f65446e13e970f46d98) | 2026-08-06 | Merge pull request #62 from spencer0124/fix/campus-eta-directions5 |
| skkuverse-ai | [`da1359a`](https://github.com/spencer0124/skkuverse-ai/commit/da1359a48545acc4b414c25ebc759f42ad0f912e) | 2026-08-05 | Merge pull request #6 from spencer0124/fix/umbrella-exported-paths |
| skkuverse-app | [`cd3c29a`](https://github.com/spencer0124/skkuverse-app/commit/cd3c29a65c8ad171e37761f8bd9ef95dd64460f8) | 2026-08-08 | Merge pull request #30 from spencer0124/fix/webview-fallback-url |
| skkuverse.com | [`85103e8`](https://github.com/spencer0124/skkuverse.com/commit/85103e8ab09f3008636e9a30010e2236531ff6e1) | 2026-06-07 | Merge branch 'dev' into main — fix miniapp deep-link scheme (triple-sla… |
| skkuverse-codepush | [`83f27d8`](https://github.com/spencer0124/skkuverse-codepush/commit/83f27d844fd54b046a511f010413527040572e86) | 2026-04-09 | chore: set TZ=Asia/Seoul in docker-compose |
| skkuverse-web | [`bb79a05`](https://github.com/spencer0124/skkuverse-web/commit/bb79a053c1598de9b0c6d8da0848f80ba30042ba) | 2026-08-09 | Merge pull request #7 from spencer0124/dev |
<!-- fleet:end -->

A pin records where `main` pointed when the snapshot ran. For where it points now, run
`sync_contracts.py check --fleet`, which reads every repo over the network. The two
disagree whenever someone has pushed since the last snapshot.

Git cannot reconstruct this after the fact, so it has to be recorded as it happens.
[ADR 0003](docs/decisions/0003-daily-fleet-pin-as-submodules.md) explains why, and
[how-to: expand a past snapshot](docs/how-to/expand-a-past-snapshot.md) covers opening a
past day. Cloning this repository does not fetch those directories, and your own checkouts
belong outside it.

## Documentation

System-wide knowledge lives in [docs/](docs/). Knowledge local to one repo lives in that
repo's own `docs/`, owned by whoever writes the thing it describes.

- [Docs index and writing rules](docs/README.md)
- [System Context](docs/architecture/system-context.md) and
  [Container View](docs/architecture/container-view.md) — the C4 levels
- [Notice Pipeline](docs/flows/notice-pipeline.md) — the AI notice feature end to end
- [Data Topology](docs/architecture/data-topology.md) — which repo owns which collection
- [Decisions](docs/decisions/) — ADRs whose consequences cross repo boundaries

Per-repo documentation: [server][skkuverse-server], [crawler][skkuverse-crawler],
[ai][skkuverse-ai], [app][skkuverse-app].

## Tooling

Stdlib-only Python 3, with no dependencies at all. The scripts split by who runs them, and
the directory says which is which.

| Directory | Who runs it | What a rename costs |
| --- | --- | --- |
| [`exported/`](exported/) | server, app and ai, in their own CI | breaks three repositories' default branches |
| [`internal/`](internal/) | only this repository | nothing outside this repo |

Consumers clone with `git clone --depth 1` and run the script using the system `python3`,
so `exported/` may never grow a third-party import.
[`exported/README.md`](exported/README.md) states the interface and what counts as a
breaking change.

```bash
# exported — the interface other repos depend on
python3 exported/sync_contracts.py status            # every contract at a glance (offline)
python3 exported/sync_contracts.py check --fleet     # freshness across every repo (network)
python3 exported/sync_contracts.py pull --all        # adopt upstream, rewrite locks
python3 exported/sync_contracts.py explain <id>      # the full chain for one contract
python3 exported/lint_conventions.py --root .        # language, frontmatter, docs structure

# internal — this repository only
python3 internal/render/fleet_table.py --check       # verify the fleet table above
python3 internal/render/contracts_table.py --check   # verify the contract table above
python3 internal/render/docs_index.py --check        # verify the document index
python3 internal/check/prose.py --root .             # bold overuse, sentence-length spread

python3 -m unittest discover -s tests -v             # every suite
```

## Contributing

Open a PR against `main`. CI runs the unit tests and validates the manifest, then verifies
both generated tables and checks this repository against the conventions it defines.
[CLAUDE.md](CLAUDE.md) lists the working constraints.

## License

[Apache-2.0](LICENSE).

[skkuverse-server]: https://github.com/spencer0124/skkuverse-server
[skkuverse-crawler]: https://github.com/spencer0124/skkuverse-crawler
[skkuverse-ai]: https://github.com/spencer0124/skkuverse-ai
[skkuverse-app]: https://github.com/spencer0124/skkuverse-app
[skkuverse.com]: https://github.com/spencer0124/skkuverse.com
[skkuverse-codepush]: https://github.com/spencer0124/skkuverse-codepush
[dotgithub]: https://github.com/spencer0124/.github
