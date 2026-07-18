"""Server-side markdown → sanitized HTML with TOC and safe doc links."""

from __future__ import annotations

import re
from typing import List, Tuple
from xml.etree import ElementTree as ET

import bleach
import markdown as md
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

from sys_des_in.tools.file_tools import is_allowed_filename

_ALLOWED_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "em",
    "strong",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "img",
]

_ALLOWED_ATTRS = {
    "a": ["href", "title", "data-doc"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
    "th": ["align"],
    "td": ["align"],
    "h1": ["id"],
    "h2": ["id"],
    "h3": ["id"],
    "h4": ["id"],
    "h5": ["id"],
    "h6": ["id"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:80] or "section"


class _HeadingIdAndDocLinkProcessor(Treeprocessor):
    def run(self, root: ET.Element) -> ET.Element:
        used: set[str] = set()
        for el in root.iter():
            tag = el.tag.lower() if isinstance(el.tag, str) else ""
            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                text = "".join(el.itertext()).strip()
                base = slugify(text)
                hid = base
                n = 2
                while hid in used:
                    hid = f"{base}-{n}"
                    n += 1
                used.add(hid)
                el.set("id", hid)
            if tag == "a":
                href = el.get("href") or ""
                name = href.split("#", 1)[0].strip()
                # Relative allowlisted markdown links → data-doc
                if name.endswith(".md") and "/" not in name and "\\" not in name:
                    if is_allowed_filename(name):
                        el.set("data-doc", name)
                        el.set("href", f"#doc={name}")
                    else:
                        el.set("href", "#")
                        if "data-doc" in el.attrib:
                            del el.attrib["data-doc"]
        return root


class _DocNavExtension(Extension):
    def extendMarkdown(self, markdown_instance: md.Markdown) -> None:  # noqa: N802
        markdown_instance.treeprocessors.register(
            _HeadingIdAndDocLinkProcessor(markdown_instance),
            "doc_nav",
            5,
        )


def render_markdown(text: str) -> Tuple[str, List[dict]]:
    """Return (sanitized_html, toc_entries)."""
    converter = md.Markdown(
        extensions=["fenced_code", "tables", "nl2br", "sane_lists", _DocNavExtension()],
        output_format="html",
    )
    raw = converter.convert(text or "")
    html = bleach.clean(
        raw,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    toc: List[dict] = []
    # Build TOC from cleaned HTML via regex (safe: ids we generated)
    for match in re.finditer(
        r"<h([1-6])\s+id=\"([^\"]+)\">(.+?)</h\1>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        level = int(match.group(1))
        hid = match.group(2)
        inner = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        if inner:
            toc.append({"id": hid, "text": inner, "level": level})
    return html, toc
