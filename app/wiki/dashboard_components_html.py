"""Shared HTML primitives for the local wiki dashboard."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from .dashboard import WikiAssignmentBubble, WikiDashboardSnapshot
from .dashboard_busy_scripts import BUSY_OVERLAY_JS
from .dashboard_position_scripts import POSITION_PERSISTENCE_JS
from .dashboard_styles import DASHBOARD_CSS
from .dashboard_toasts import render_toast
from .provider_balances import (
    ProviderBalance,
    provider_balance_value,
    provider_label,
)

_SHARED_SCRIPTS = (
    "<script>\n"
    + BUSY_OVERLAY_JS
    + """
document.addEventListener("submit", function (event) {
  var form = event.target.closest('form[data-confirm]');
  if (!form) return;
  var message = form.getAttribute("data-confirm") || "Are you sure?";
  if (!window.confirm(message)) {
    event.preventDefault();
    event.stopPropagation();
  }
});
"""
    + POSITION_PERSISTENCE_JS
    + """
(function () {
  var t = document.getElementById("toast");
  if (!t) return;
  setTimeout(function () {
    t.classList.add("toast-out");
    setTimeout(function () { t.remove(); }, 300);
  }, 4000);
})();
</script>
"""
)


STATUS_LABELS = {
    "current": "Current",
    "needs_review": "Needs review",
    "needs_build": "Needs build",
    "accepted": "Accepted",
    "rejected": "Rejected",
    "pending": "Needs review",
    "stale accepted": "Needs review",
    "stale rejected": "Needs review",
}


def render_dashboard_page(
    *,
    document_title: str,
    page_heading: str,
    snapshot: WikiDashboardSnapshot,
    provider_balances: tuple[ProviderBalance, ...],
    message: str,
    body: str,
    message_type: str = "",
    scripts: str = "",
    back_href: str = "",
) -> str:
    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(document_title)}</title>",
            '<link rel="preconnect" href="https://fonts.googleapis.com">',
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
            '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">',
            f"<style>{DASHBOARD_CSS}</style>",
            "</head>",
            "<body>",
            "<main>",
            render_dashboard_header(
                snapshot, provider_balances, page_heading, back_href=back_href,
            ),
            body,
            "</main>",
            render_toast(message, message_type),
            render_busy_overlay(),
            _SHARED_SCRIPTS,
            scripts,
            "</body>",
            "</html>",
        )
    )


def render_dashboard_header(
    snapshot: WikiDashboardSnapshot,
    provider_balances: tuple[ProviderBalance, ...],
    page_heading: str,
    *,
    back_href: str = "",
) -> str:
    review = sum(1 for row in snapshot.wikis if "needs_review" in row.state)
    build = sum(1 for row in snapshot.wikis if "needs_build" in row.state)
    back_link = (
        f'<a class="back-link" href="{escape(back_href)}" aria-label="Back" title="Back">{BACK_ICON}</a>'
        if back_href
        else ""
    )
    return f"""
<header class="topbar">
  <div>
    <div class="topbar-brand">
      {back_link}
      <a class="wordmark" href="/" aria-label="MEMEX — dashboard">MEMEX</a>
    </div>
    <h1>{escape(page_heading)}</h1>
  </div>
  <div class="topbar-side">
    <div class="metrics">
      {_metric("Wikis", len(snapshot.wikis))}
      {_metric("Fact Review", review)}
      {_metric("Wiki Build", build)}
      {_metric("Sources", len(snapshot.sources))}
    </div>
    {_render_provider_balances(provider_balances)}
  </div>
</header>
"""


def render_busy_overlay(
    *,
    title: str = "Working",
    detail: str = "This may take a moment.",
) -> str:
    return f"""
<div class="busy-overlay" id="memex-busy-loader" hidden role="status" aria-live="polite">
  <div class="busy-panel">
    <div class="busy-spinner" aria-hidden="true"></div>
    <p class="busy-title" data-busy-title>{escape(title)}</p>
    <p class="busy-detail" data-busy-detail>{escape(detail)}</p>
  </div>
</div>
"""


def render_source_assignment_bubble(
    source_id: str,
    bubble: WikiAssignmentBubble,
    query: str = "",
    return_to: str = "",
) -> str:
    operation = "unassign" if bubble.assigned else "assign"
    symbol = "-" if bubble.assigned else "+"
    action = "Remove" if bubble.assigned else "Assign"
    classes = "bubble"
    if bubble.assigned:
        classes += " assigned"
    classes += state_class(bubble.state)
    location = return_to or (f"/?{query}" if query else "/")
    title = f"{action} {bubble.title}; {display_label(bubble.state)}"
    aria_label = f"{action} {bubble.title}"
    return f"""
<form method="post" action="/assign">
  {hidden_input("source_id", source_id)}
  {hidden_input("wiki_id", bubble.wiki_id)}
  {hidden_input("operation", operation)}
  {hidden_input("return_to", location)}
  <button type="submit" class="{classes}" title="{escape(title)}" aria-label="{escape(aria_label)}">
    <span class="bubble-symbol">{symbol}</span><span class="bubble-label">{escape(bubble.wiki_id)}</span>
  </button>
</form>
"""


CLOSE_ICON = (
    '<svg class="button-icon-svg" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="1.6"'
    ' stroke-linecap="round"/></svg>'
)

BACK_ICON = (
    '<svg class="button-icon-svg back-icon-svg" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M5 8l6-5v10z" fill="currentColor"/>'
    '</svg>'
)


def render_delete_wiki_form(wiki_id: str, title: str) -> str:
    return _render_delete_form(
        action="/delete-wiki",
        hidden_fields=(("wiki_id", wiki_id),),
        label="Delete wiki",
        form_class="wiki-delete-form",
        confirm=f"Delete the wiki \u201c{title}\u201d? This cannot be undone.",
        icon=False,
    )


def render_delete_source_form(
    source_id: str,
    label: str = "Delete source",
) -> str:
    return _render_delete_form(
        action="/delete-source",
        hidden_fields=(("source_id", source_id),),
        label=label,
        form_class="source-delete-form",
        source_delete_tracking=True,
        icon=False,
    )


def _render_delete_form(
    *,
    action: str,
    hidden_fields: tuple[tuple[str, str], ...],
    label: str,
    form_class: str,
    source_delete_tracking: bool = False,
    confirm: str = "",
    icon: bool,
) -> str:
    tracking_attr = ' data-source-delete-form="1"' if source_delete_tracking else ""
    confirm_attr = f' data-confirm="{escape(confirm, quote=True)}"' if confirm else ""
    button = (
        render_icon_button(label, icon=CLOSE_ICON, variant="danger", raw=True)
        if icon
        else f'<button type="submit" class="button button-danger delete-button">{escape(label)}</button>'
    )
    fields = "\n  ".join(hidden_input(name, value) for name, value in hidden_fields)
    return f"""
<form method="post" action="{escape(action, quote=True)}" class="{escape(form_class, quote=True)}"{tracking_attr}{confirm_attr}>
  {fields}
  {button}
</form>
"""


def render_icon_button(
    label: str,
    *,
    icon: str,
    name: str = "",
    value: str = "",
    variant: str = "default",
    title: str = "",
    raw: bool = False,
) -> str:
    name_attr = f' name="{escape(name)}"' if name else ""
    value_attr = f' value="{escape(value)}"' if value else ""
    variant_class = {
        "save": "button-save save-icon",
        "danger": "button-danger danger-icon",
    }.get(variant, "")
    icon_html = icon if raw else escape(icon)
    return (
        f'<button type="submit" class="button button-icon icon-button {variant_class}"'
        f'{name_attr}{value_attr} title="{escape(title or label)}"'
        f' aria-label="{escape(label)}">{icon_html}</button>'
    )


def render_status_pill(state: str) -> str:
    if state == "current":
        return ""
    return f'<span class="pill{state_class(state)}">{escape(display_label(state))}</span>'


def repair_hidden_fields(source_id: str) -> str:
    return "\n".join(
        (
            hidden_input("partial_repair", "1"),
            hidden_input("source_id", source_id),
        )
    )


def hidden_input(name: str, value: str) -> str:
    return f'<input type="hidden" name="{escape(name)}" value="{escape(value, quote=True)}">'


def source_detail_path(source_id: str) -> str:
    return "/source/" + quote(source_id, safe="")


def wiki_detail_path(wiki_id: str) -> str:
    return "/wiki/" + quote(wiki_id, safe="")


def wiki_facts_path(wiki_id: str) -> str:
    return wiki_detail_path(wiki_id) + "/facts"


def textarea_rows(text: str, *, minimum: int, maximum: int) -> int:
    lines = text.splitlines() or [""]
    visual_rows = sum(max(1, (len(line) + 83) // 84) for line in lines)
    return min(maximum, max(minimum, visual_rows))


def display_label(value: str) -> str:
    if value in STATUS_LABELS:
        return STATUS_LABELS[value]
    words = value.replace("_", " ").replace("+", " + ")
    return " ".join(word.capitalize() if word != "+" else word for word in words.split())


def css_token(value: str) -> str:
    token = "".join(char for char in value if char.isalnum() or char in ("-", "_"))
    return token or "unknown"


def state_class(state: str) -> str:
    if state == "current":
        return ""
    return f" state-{escape(state)}"


def pluralize(count: int, singular: str) -> str:
    return f"{count} {singular}{'s' if count != 1 else ''}"


def _render_provider_balances(provider_balances: tuple[ProviderBalance, ...]) -> str:
    if not provider_balances:
        return ""
    chips = "\n".join(_render_provider_balance(balance) for balance in provider_balances)
    return f'<div class="balances">{chips}</div>'


def _render_provider_balance(balance: ProviderBalance) -> str:
    status = css_token(balance.status)
    title = escape(balance.detail or provider_balance_value(balance))
    card_value = provider_balance_value(balance) if balance.amount is not None else "Balance"
    content = f"""
  <span>{escape(provider_label(balance.provider))}</span>
  <strong>{escape(card_value)}</strong>
"""
    if balance.url:
        return f"""
<a class="balance-chip balance-{status}" title="{title}" href="{escape(balance.url)}" target="_blank" rel="noopener noreferrer">
{content}</a>
"""
    return f"""
<div class="balance-chip balance-{status}" title="{title}">
{content}
</div>
"""


def _metric(label: str, value: int) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{value}</strong></div>'
