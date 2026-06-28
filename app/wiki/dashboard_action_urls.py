"""Redirect URL helpers for dashboard actions."""

from __future__ import annotations

from urllib.parse import quote, urlencode


def dashboard_location(message: str) -> str:
    return "/?" + urlencode({"message": message})


def source_detail_location(source_id: str, message: str) -> str:
    return "/source/" + quote(source_id, safe="") + "?" + urlencode({"message": message})
