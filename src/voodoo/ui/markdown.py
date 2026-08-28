"""Safe minimal Markdown renderer (dependency-free).

Renders the subset real chat/agent UIs need — headings, emphasis, inline
code, fenced code blocks, lists, blockquotes, links, paragraphs, hard
breaks — while escaping ALL raw HTML in the source. Used by the
:class:`~voodoo.ui.library.Markdown` component.

Deliberately NOT a full CommonMark implementation: the goal is safe,
predictable output for model-generated text, not spec completeness.
"""

from __future__ import annotations

import html
import re

__all__ = ["render_markdown"]

_FENCE_RE = re.compile(r"^```(\w*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_ListItem_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.+)$")


def _is_structural(line: str) -> bool:
    """True when a line starts a new block (not paragraph content)."""
    return bool(
        line.startswith(">")
        or _HEADING_RE.match(line)
        or _FENCE_RE.match(line.strip())
        or _ListItem_RE.match(line)
    )


def _inline(text: str) -> str:
    """Render inline markup (escaped): **bold**, *italic*, `code`, [link](url)."""
    escaped = html.escape(text, quote=True)

    # Inline code first (protect its contents from further processing).
    parts: list[str] = []

    def _stash(match: re.Match[str]) -> str:
        parts.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(parts) - 1}\x00"

    escaped = re.sub(r"`([^`]+)`", _stash, escaped)

    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", escaped)

    return re.sub("\x00(\\d+)\x00", lambda m: parts[int(m.group(1))], escaped)


def render_markdown(source: str) -> str:
    """Render a Markdown subset to an HTML fragment (fully escaped input)."""
    out: list[str] = []
    lines = source.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Fenced code block
        fence = _FENCE_RE.match(line.strip())
        if fence:
            i = _render_code_fence(lines, i, fence, out)
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote (consume consecutive quote lines)
        if line.startswith(">"):
            quote_lines = []
            while i < n and lines[i].startswith(">"):
                quote_lines.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote_lines))}</blockquote>")
            continue

        # Lists (consume consecutive items)
        if _ListItem_RE.match(line):
            i = _render_list(lines, i, out)
            continue

        # Blank line
        if not line.strip():
            i += 1
            continue

        # Paragraph (consume until blank/structural line)
        para: list[str] = []
        while i < n and lines[i].strip() and not _is_structural(lines[i]):
            para.append(lines[i])
            i += 1
        # Hard breaks within a paragraph (two trailing spaces or backslash).
        joined = "<br/>".join(_inline(p.rstrip(" \\")) for p in para)
        out.append(f"<p>{joined}</p>")

    return "\n".join(out)


def _render_code_fence(
    lines: list[str], i: int, fence: re.Match[str], out: list[str]
) -> int:
    """Consume a fenced code block; return the next line index."""
    lang = fence.group(1)
    code_lines: list[str] = []
    i += 1
    n = len(lines)
    while i < n and not lines[i].strip().startswith("```"):
        code_lines.append(lines[i])
        i += 1
    i += 1  # consume closing fence
    cls = f' class="language-{html.escape(lang)}"' if lang else ""
    body = html.escape("\n".join(code_lines), quote=True)
    out.append(f"<pre><code{cls}>{body}</code></pre>")
    return i


def _render_list(lines: list[str], i: int, out: list[str]) -> int:
    """Consume a consecutive list block; return the next line index."""
    first = _ListItem_RE.match(lines[i])
    assert first is not None  # caller guarantees a match
    ordered = first.group(2) not in ("-", "*", "+")
    tag = "ol" if ordered else "ul"
    items: list[str] = []
    n = len(lines)
    while i < n:
        lm = _ListItem_RE.match(lines[i])
        if not lm:
            break
        items.append(f"<li>{_inline(lm.group(3))}</li>")
        i += 1
    out.append(f"<{tag}>{''.join(items)}</{tag}>")
    return i
