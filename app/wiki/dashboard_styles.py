"""CSS assets for the local wiki dashboard."""

from __future__ import annotations

from pathlib import Path

CSS_ASSET_NAMES = (
    "base.css",
    "ingest.css",
    "home.css",
    "source-detail.css",
    "responsive.css",
    "wiki-page.css",
)


def load_dashboard_css(asset_names: tuple[str, ...] = CSS_ASSET_NAMES) -> str:
    asset_dir = Path(__file__).with_name("assets") / "css"
    return "\n".join(
        (asset_dir / asset_name).read_text(encoding="utf-8").strip() for asset_name in asset_names
    )


DASHBOARD_CSS = load_dashboard_css()
