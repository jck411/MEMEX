"""HTML rendering for built wiki markdown pages."""

from __future__ import annotations

import re
from html import escape, unescape

from .dashboard import WikiDashboardSnapshot
from .dashboard_components_html import (
    render_dashboard_page,
    render_status_pill,
    wiki_facts_path,
)
from .provider_balances import ProviderBalance
from .records import WikiRecord
from .status import WikiStatus

_GENERATED_ANCHOR_RE = re.compile(r'<a id="(memex-fact-[A-Za-z0-9_.:-]+)"></a>')
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^()\s]+)\)")
_FRAGMENT_LINK_RE = re.compile(r"#[A-Za-z0-9_.:-]+")
_SOURCE_LINK_RE = re.compile(r"/source/[A-Za-z0-9_.~%-]+")
_RELATIVE_LINK_RE = re.compile(
    r"(?:[A-Za-z0-9_.~%-]+/)*[A-Za-z0-9_.~%-]+(?:#[A-Za-z0-9_.:-]+)?"
)


def render_wiki_page_html(
    *,
    snapshot: WikiDashboardSnapshot,
    wiki: WikiRecord,
    status: WikiStatus,
    markdown: str,
    provider_balances: tuple[ProviderBalance, ...] = (),
    message: str = "",
    message_type: str = "",
) -> str:
    state = render_status_pill(_status_state(status))
    facts_link = f'<a class="button" href="{wiki_facts_path(wiki.wiki_id)}">Facts Used</a>'
    body = f"""
<section class="section wiki-view">
  <div class="wiki-view-heading">
    <div>
      <p class="eyebrow">Wiki</p>
      <h2>{escape(wiki.title)}</h2>
      <p class="muted">{escape(wiki.wiki_id)} · {escape(wiki.path)}</p>
    </div>
    <div class="wiki-view-actions">{state}{facts_link}</div>
  </div>
  {_render_wiki_body(markdown, wiki.title)}
</section>
"""
    return render_dashboard_page(
        document_title=f"{wiki.title} - MEMEX Wiki",
        page_heading="Wiki Detail",
        snapshot=snapshot,
        provider_balances=provider_balances,
        message=message,
        message_type=message_type,
        body=body,
        back_href="/",
    )


def _status_state(status: WikiStatus) -> str:
    if status.needs_review:
        return "needs_review"
    if status.needs_build:
        return "needs_build"
    return "current"


def _render_wiki_body(markdown: str, wiki_title: str) -> str:
    if not markdown.strip():
        return '<p class="empty">No built wiki page yet.</p>'
    display_markdown = _without_duplicate_title(markdown, wiki_title)
    return f'<article class="wiki-document">{_render_markdown(display_markdown)}</article>'


def _without_duplicate_title(markdown: str, wiki_title: str) -> str:
    title = _normalized_heading_text(wiki_title)
    if not title:
        return markdown

    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or _is_generated_comment(stripped):
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if (
            heading
            and heading.group(1) == "#"
            and _normalized_heading_text(heading.group(2)) == title
        ):
            return "\n".join(lines[:index] + lines[index + 1 :])
        return markdown
    return markdown


def _render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    paragraph: list[str] = []
    list_open: str | None = None
    quote: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            html.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html.append(f"</{list_open}>")
            list_open = None

    def open_list(tag: str) -> None:
        nonlocal list_open
        if list_open == tag:
            return
        close_list()
        html.append(f"<{tag}>")
        list_open = tag

    def flush_quote() -> None:
        nonlocal quote
        if quote:
            body = "".join(f"<p>{_inline(line)}</p>" for line in quote)
            html.append(f"<blockquote>{body}</blockquote>")
            quote = []

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped or _is_generated_comment(stripped):
            flush_paragraph()
            close_list()
            flush_quote()
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            flush_quote()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            html.append(f"<pre><code>{escape(chr(10).join(code))}</code></pre>")
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            close_list()
            flush_quote()
            level = len(heading.group(1))
            html.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        bullet = re.match(r"^\s*[-*]\s+(.+)$", raw_line)
        if bullet:
            flush_paragraph()
            flush_quote()
            open_list("ul")
            html.append(f"<li>{_inline(bullet.group(1))}</li>")
            index += 1
            continue

        numbered = re.match(r"^\s*\d+\.\s+(.+)$", raw_line)
        if numbered:
            flush_paragraph()
            flush_quote()
            open_list("ol")
            html.append(f"<li>{_inline(numbered.group(1))}</li>")
            index += 1
            continue

        quoted = re.match(r"^>\s?(.*)$", stripped)
        if quoted:
            flush_paragraph()
            close_list()
            quote.append(quoted.group(1))
            index += 1
            continue

        close_list()
        flush_quote()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    close_list()
    flush_quote()
    return "".join(html)


def _inline(text: str) -> str:
    pieces = re.split(r'(`[^`]*`|<a id="memex-fact-[A-Za-z0-9_.:-]+"></a>)', text)
    rendered: list[str] = []
    for piece in pieces:
        if piece.startswith("`") and piece.endswith("`"):
            rendered.append(f"<code>{escape(piece[1:-1])}</code>")
        elif _GENERATED_ANCHOR_RE.fullmatch(piece):
            anchor_id = _GENERATED_ANCHOR_RE.fullmatch(piece).group(1)
            rendered.append(f'<a id="{escape(anchor_id, quote=True)}"></a>')
        else:
            rendered.append(_markdown_links(_strong(escape(piece))))
    return "".join(rendered)


def _strong(text: str) -> str:
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def _markdown_links(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        href = unescape(match.group(2))
        if not _is_internal_href(href):
            return match.group(0)
        return f'<a href="{escape(href, quote=True)}">{label}</a>'

    return _MARKDOWN_LINK_RE.sub(replace, text)


def _is_internal_href(href: str) -> bool:
    if _FRAGMENT_LINK_RE.fullmatch(href) or _SOURCE_LINK_RE.fullmatch(href):
        return True
    if not _RELATIVE_LINK_RE.fullmatch(href):
        return False
    path = href.split("#", 1)[0]
    return all(part not in {".", ".."} for part in path.split("/"))


def _normalized_heading_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def _is_generated_comment(line: str) -> bool:
    return line.startswith("<!--") and line.endswith("-->")
