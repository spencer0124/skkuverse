"""Generate skkuverse-app's tab-key mirror from the server categories artifact.

The app's Cloud Function needs to know which notice tabs exist: `fixed` tabs
become one FCM topic each, `picker` tab keys double as topic prefixes. That
list was hand-typed, and the documented footgun was that adding a *fixed* tab
without updating the mirror is undetectable — `derive()` warns on an unknown
picker key, but a missing fixed key just means that tab's subscribers silently
receive nothing.

Only the keys are generated. MAX_TOPICS stays hand-owned in tabsContract.ts:
it is an app-side decision bounded by Firestore's array-contains-any limit,
and it flows app -> server, the opposite direction from these keys.
"""

from __future__ import annotations

import json
import re

# A picker tab's key IS its topic prefix ('dept' -> 'dept:<id>'), so a key
# containing ':' or '/' would corrupt every topic string it appears in.
TOPIC_KEY_RE = re.compile(r"[a-z][a-z0-9]*")

HEADER = """\
// GENERATED — do not edit.
//
// Source: skkuverse-crawler py/generated/server-categories.json
// Regenerate: python3 <skkuverse>/tools/skkuverse_sync.py pull --repo app
// Hash-locked in .contracts.lock.json ("notices.tab-keys"); CI fails on drift.

"""


class GeneratorError(Exception):
    pass


def _block(name: str, keys: list[str]) -> str:
    body = "".join(f"  '{key}',\n" for key in keys)
    return f"export const {name} = [\n{body}] as const;\n"


def tabs_contract_ts(producer_bytes: bytes) -> bytes:
    categories = json.loads(producer_bytes.decode("utf-8"))

    fixed = [c["id"] for c in categories if c["tabMode"] == "fixed"]
    picker = [c["id"] for c in categories if c["tabMode"] == "picker"]

    if not fixed or not picker:
        raise GeneratorError(
            f"expected both fixed and picker tabs, got "
            f"{len(fixed)} fixed / {len(picker)} picker — an empty picker set "
            f"would silently disable all picker notifications"
        )

    for key in fixed + picker:
        if not TOPIC_KEY_RE.fullmatch(key):
            raise GeneratorError(
                f"category id {key!r} is not a valid FCM topic prefix "
                f"(picker key === topic prefix, identity mapping)"
            )

    overlap = set(fixed) & set(picker)
    if overlap:
        raise GeneratorError(
            f"id(s) in both modes: {sorted(overlap)} — derive() would emit two "
            f"topic shapes for one tab"
        )

    return (
        HEADER
        + _block("FIXED_TAB_KEYS", fixed)
        + "\n"
        + _block("KNOWN_PICKER_KEYS", picker)
    ).encode("utf-8")
