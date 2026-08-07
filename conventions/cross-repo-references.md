---
title: Cross-Repository References
type: reference
status: accepted
owner: zoyoong124@gmail.com
last-updated: 2026-08-07
audience: public
---

# Cross-repository references

> How to link across SKKUverse repositories, and why an unqualified reference resolves to
> the wrong object rather than failing visibly.

## Summary

Tracking issues live in this repository. The code that closes them lives in
[skkuverse-server](https://github.com/spencer0124/skkuverse-server),
[skkuverse-app](https://github.com/spencer0124/skkuverse-app) and their siblings. Every
reference between the two crosses a repository boundary, and GitHub resolves `#123` against
the repository the text is in.

| Target | Correct form | What the short form does instead |
| --- | --- | --- |
| Issue or PR elsewhere | `spencer0124/skkuverse#13` | `#13` resolves inside the current repo; `skkuverse#13` is plain text |
| Commit elsewhere | `spencer0124/skkuverse-server@70d1ddd` | a bare SHA renders as text and links nowhere |
| Closing an issue elsewhere | `Closes spencer0124/skkuverse#14` | closes on merge into the **source** repo's default branch |

The owner segment is required. GitHub documents `Username/Repository#number` as the
cross-repository form, and a repository name on its own has no meaning to the autolinker.

## Why an unqualified reference is a defect

A reference that fails to resolve is visible: the reader sees plain text and goes looking.
A reference that resolves to the wrong object is not.

Both `skkuverse` and `skkuverse-server` number their issues and pull requests from one.
This repository's event map epic is `#11` and its phase issues run from `#12`.
`skkuverse-server` already merged pull requests at those same numbers. A commit in the
server repo that says `#14` links to "fix: instagram deeplink", and GitHub posts a
reference event onto that unrelated pull request. Nothing reports an error. The link works,
points somewhere plausible, and misinforms every reader after that.

Both repositories keep counting, so the overlap widens with every issue either one opens.

## Backticks suppress linking

A code span is never autolinked. This renders as literal text:

```markdown
`spencer0124/skkuverse-server@70d1ddd`
```

Write the reference bare, and reserve backticks for identifiers, paths and commands. The
same applies inside issue bodies, comments and pull request descriptions.

## Checklist before pushing

Run this against the commits about to leave the machine:

```bash
git log --format=%B origin/<branch>..HEAD \
  | grep -oE '(^|[^/A-Za-z0-9_.-])[a-zA-Z-]*#[0-9]+'
```

Anything it prints is unqualified, since a correct reference contains a slash.

- [ ] Every issue reference in an outgoing commit reads `owner/repo#number`
- [ ] Every commit reference in an issue or comment reads `owner/repo@sha`
- [ ] No reference sits inside backticks
- [ ] Any SHA quoted in an issue still exists, if the branch was rebased
- [ ] Closing keywords name the repository that owns the issue

Do this before pushing. Correcting a message afterwards means rewriting published history
on a shared branch.

## Rewording unpushed commits

Messages can be corrected without an interactive rebase, which matters where `rebase -i` is
unavailable. Replay the range onto its upstream and amend each message in turn:

```bash
git checkout --detach origin/dev
while read -r sha; do
  git cherry-pick -n "$sha"
  git commit -F "message-for-$sha.txt"
done < shas.txt
git diff <old-head> HEAD     # must print nothing
git branch -f dev HEAD
```

The verification step is the important one. It proves the rewrite changed only messages.

Reaching for `git reset --soft` and re-staging by path looks simpler and quietly corrupts
any range where two commits touch the same file: staging a path takes that file's final
content, so the earlier commit absorbs the later one's changes and the later commit ends up
empty.

## Related

- [README.md](README.md) — how shared conventions are defined and enforced
- [Autolinked references](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls) — GitHub's own table of forms
- [Linking a pull request to an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) — closing keywords, including across repositories
