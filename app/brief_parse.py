"""Parse design_context brief markdown into structured sections."""

from __future__ import annotations

import re
from typing import Dict, Optional

from .schemas import BriefOut

# Maps ### Heading -> BriefOut field
_HEADING_MAP = {
    "problem": "problem",
    "critical flows": "critical_flows",
    "scale": "scale",
    "quality targets": "quality_targets",
    "constraints": "constraints",
    "maturity": "maturity",
    "must-have features": "must_haves",
    "must-haves": "must_haves",
    "out of scope": "out_of_scope",
    "reasoning": "reasoning",
}

_HEADING_RE = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)


def parse_brief_sections(markdown: Optional[str]) -> Optional[BriefOut]:
    """Split brief markdown on ## / ### headings into BriefOut fields."""
    if not markdown or not markdown.strip():
        return None
    text = markdown.strip()
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return BriefOut(problem=text[:2000] if text else None)

    sections: Dict[str, str] = {}
    for i, match in enumerate(matches):
        title = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        key = _HEADING_MAP.get(title)
        if key and body:
            sections[key] = body[:4000]

    if not sections:
        return None
    return BriefOut(**sections)
