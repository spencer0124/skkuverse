---
title: Issue Tracking
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-07
audience: public
---

# Issue tracking

> Every issue in the fleet is filed in the umbrella repository, and GitHub's tracking
> primitives each carry one axis of the work. This page says which axis goes where, and what
> breaks when they are swapped.

## One tracker for the fleet

Issues are opened in [the umbrella](https://github.com/spencer0124/skkuverse/issues) whatever
repository the change is made in. Sibling repositories keep their issue tabs enabled so their
closed history stays readable, and the shared template config in
[`spencer0124/.github`](https://github.com/spencer0124/.github) links back here.

Most work in this ecosystem is not repo-shaped. One change often reaches the server, the app
and the webview together. An issue filed in any one of them then describes a fraction of
itself. Filing centrally also removes the constraint that a milestone cannot span
repositories, which makes the rest of this page workable.

The cost is that `area:` labels carry routing that a repository name would otherwise supply
for free.

## Which primitive carries which axis

| Axis | Where it lives | Per issue |
| --- | --- | --- |
| What kind of thing this is | Label `bug`, `task`, `enhancement`, `documentation` | one |
| Which surfaces the change reaches | Label `area:*` | any number |
| Whether it is a tracking issue | Label `epic`, plus native sub-issues | one |
| Which dated batch it is released with | Milestone | one |
| Where it currently stands | Project field `Status` | one |
| Which stream of work it belongs to | Project field `Track` | one |
| How someone wants to read the list today | View | any number |

That table follows from where each primitive is stored. Labels and milestones are held on the
issue and survive without the project, so anything `gh` or a workflow has to read belongs
there. Project fields are held beside the issue, which is what lets them change often without
adding to the issue's own history.

**State never becomes a label.** A `status:` label has to be moved by hand every time work
moves, and one missed edit makes the rest untrustworthy. `Status` is a project field because a
project workflow can maintain it without anyone remembering to.

## The `area:` axis

`area:` names the surface a change is made to. It does not name the repository holding the
issue, because that is always this one.

An issue carries as many values as apply. No other primitive here is many-to-many, since a
milestone holds one value and so does a project single-select field. An issue that changes the
server, the app and the webview is described accurately only by three labels.

Surfaces smaller than a repository get a value where the distinction does work.
`area:webview` and `area:console` both live inside web repositories, and both earn separating
because their release paths differ.

## Milestones are dated batches

A milestone answers when a batch reaches users. Each issue holds one, and that limit does the
useful work: it forces every issue to name the single release it belongs to.

The ESKARA milestones split on whether a change has to clear app store review. That festival
runs with no store release while it is live, the central claim of
[#11](https://github.com/spencer0124/skkuverse/issues/11), so anything inside the app bundle
faces an earlier deadline than anything served over the network. Sorting the phases across
those two milestones tests the claim. A phase that resists the sort has found a leak in it.

Dates and membership live on the
[milestones page](https://github.com/spencer0124/skkuverse/milestones), never here, for the
reason given in [prose.md](prose.md#what-no-linter-can-decide).

An undated milestone used as a category spends the one slot an issue has and buys grouping
that a project field gives away. Work with no release date takes no milestone.

## The project and its views

[The SKKUverse project](https://github.com/users/spencer0124/projects) holds every open issue
and adds what labels and milestones cannot express.

| Field | Type | Carries |
| --- | --- | --- |
| `Status` | single select | Backlog, Ready, In progress, In review, Blocked, Done |
| `Track` | single select | Which stream the work belongs to, cutting across `area:` and milestone |
| `Target` | date | Feeds the roadmap layout |
| `Size` | single select | Rough cost, maintained by hand |

`Repository`, `Labels`, `Milestone` and sub-issue progress arrive as read-only columns the
project reads from each issue. Nothing on that list is re-entered by hand, and re-entering any
of it would create a second copy to keep true.

Built-in workflows keep the project current. A newly opened issue is added automatically.
Closing an issue, or merging its linked pull request, sets `Status` to Done.

Views are saved combinations of layout, filter, grouping and sort. They hold no data, so
deleting one loses nothing, and the sensible number is however many questions get asked. Views
can only be created in the browser, since the API exposes them read-only.

## Filing an issue

Open it in the umbrella, from the `Bug` or `Task` template. Then add every `area:` value the
change reaches, a milestone if a release date is already known, and a `Track` once the project
picks it up.

For a body of work spanning more than a week, add `epic` and split it into native sub-issues.
Sub-issues give a parent progress bar without spending its milestone slot, so phase breakdowns
use them rather than task lists.

## Traps worth knowing

**Milestone due dates move by a day.** The API interprets `due_on` against a timezone, so
midnight UTC stores the previous date. Send midday and read the response back:

```bash
gh api repos/spencer0124/skkuverse/milestones \
  -f title="..." -f due_on="2026-08-27T12:00:00Z" --jq .due_on
```

**Transferring an issue drops labels the destination lacks.** `gh issue transfer` keeps the
body, the comments and a redirect from the old number, and silently discards any label absent
by that name. Re-apply labels afterwards.

**An issue template can only apply a label that exists.** `task.yml` in
[`spencer0124/.github`](https://github.com/spencer0124/.github) declares `labels: [task]`, and
any repository lacking a `task` label drops it without warning.

**Default labels reach new repositories only.** Account-level defaults are copied at repository
creation and never synced afterwards, so a label added here never appears in a sibling. Under
one tracker that stays harmless.

## Related

- [README.md](README.md) — how shared conventions split between contracts and linters
- [branching.md](branching.md) — where the work happens once an issue exists
- [cross-repo-references.md](cross-repo-references.md) — referring to an issue from another repository
