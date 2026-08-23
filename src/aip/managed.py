"""Helpers for the aip-managed block inside otherwise human-owned files (AGENTS.md, CLAUDE.md).

aip only ever owns the fenced region between the BEGIN/END markers. Everything a human
writes outside that region is preserved verbatim across re-runs.
"""

from __future__ import annotations

import re

BEGIN_PREFIX = "<!-- AIP:BEGIN"
END_MARKER = "<!-- AIP:END -->"

_BLOCK_RE = re.compile(
    r"<!-- AIP:BEGIN[^\n]*-->\n.*?\n<!-- AIP:END -->",
    re.DOTALL,
)


def make_block(content: str, version: int) -> str:
    """Return the exact managed block string for the given content + standard version."""
    return f"<!-- AIP:BEGIN standard_version={version} -->\n{content}\n{END_MARKER}"


def has_block(text: str) -> bool:
    return bool(_BLOCK_RE.search(text))


def block_matches(text: str, block: str) -> bool:
    """True if the file already contains exactly this managed block."""
    return block in text


def upsert_block(text: str, block: str) -> str:
    """Replace an existing managed block with ``block``, or append it if none exists.

    Human content outside the block is untouched.
    """
    if _BLOCK_RE.search(text):
        return _BLOCK_RE.sub(lambda _: block, text, count=1)
    sep = "" if text == "" or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return f"{text}{sep}{block}\n"
