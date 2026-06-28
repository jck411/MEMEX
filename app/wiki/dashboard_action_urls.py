"""Redirect URL helpers for dashboard actions."""

from __future__ import annotations

from urllib.parse import quote, urlencode


def dashboard_location(message: str, *, message_type: str = "") -> str:
    return "/?" + urlencode(_message_params(message, message_type))


def source_detail_location(
    source_id: str,
    message: str,
    *,
    message_type: str = "",
) -> str:
    return (
        "/source/"
        + quote(source_id, safe="")
        + "?"
        + urlencode(_message_params(message, message_type))
    )


def _message_params(message: str, message_type: str) -> dict[str, str]:
    params = {"message": message}
    if message_type:
        params["message_type"] = message_type
    return params
