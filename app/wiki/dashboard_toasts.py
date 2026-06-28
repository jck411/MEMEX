"""Dashboard toast rendering."""

from __future__ import annotations

from html import escape

TOAST_TYPES = {"info", "success", "error"}


def normalize_toast_type(value: str) -> str:
    toast_type = value.strip().lower()
    return toast_type if toast_type in TOAST_TYPES else "info"


def render_toast(message: str, message_type: str = "") -> str:
    if not message:
        return ""
    toast_type = normalize_toast_type(message_type)
    role = "alert" if toast_type == "error" else "status"
    aria_live = "assertive" if toast_type == "error" else "polite"
    classes = f"toast toast-{toast_type}"
    return (
        f'<div id="toast" class="{classes}" role="{role}" aria-live="{aria_live}">'
        f"{escape(message)}"
        '<button type="button" class="toast-close" aria-label="Dismiss" '
        "onclick=\"document.getElementById('toast')?.remove()\">&times;</button>"
        "</div>"
    )
