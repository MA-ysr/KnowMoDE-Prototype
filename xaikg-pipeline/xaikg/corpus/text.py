"""Text normalisation shared by the fetchers: HTML stripping and whitespace tidying. Documents are
stored as plain UTF-8 text with blank lines between paragraphs (what the PARAGRAPH splitter expects)."""
from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_NL = re.compile(r"\n{3,}")


def strip_html(s: str) -> str:
    s = re.sub(r"(?i)<\s*br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</\s*(p|div|li|h[1-6]|tr|table|ul|ol)\s*>", "\n\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    return tidy(s)


def tidy(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = _WS.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = _NL.sub("\n\n", s)
    return s.strip()


def section(title: str, body: str) -> str:
    body = tidy(body)
    return f"## {title}\n\n{body}\n\n" if body else ""
