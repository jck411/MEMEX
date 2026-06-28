"""Public workspace facade for wiki workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .storage import WikiDataStore
from .workspace_assignments import WorkspaceAssignmentMixin
from .workspace_builds import BuildWorkflowResult, WorkspaceBuildMixin
from .workspace_reviews import ReviewWorkflowResult, WorkspaceReviewMixin
from .workspace_sources import SourceImportResult, WorkspaceSourceMixin
from .workspace_views import WorkspaceViewMixin
from .workspace_wikis import WorkspaceWikiMixin

__all__ = [
    "BuildWorkflowResult",
    "ReviewWorkflowResult",
    "SourceImportResult",
    "WikiWorkspace",
    "workspace_for_repo",
]


@dataclass(frozen=True)
class WikiWorkspace(
    WorkspaceWikiMixin,
    WorkspaceSourceMixin,
    WorkspaceAssignmentMixin,
    WorkspaceReviewMixin,
    WorkspaceBuildMixin,
    WorkspaceViewMixin,
):
    data_store: WikiDataStore
    vault_root: Path | str

    def __post_init__(self) -> None:
        object.__setattr__(self, "vault_root", Path(self.vault_root))


def workspace_for_repo(
    repo_root: str | Path = ".",
    data_dir: str = "data",
    vault_dir: str = "vault",
) -> WikiWorkspace:
    root = Path(repo_root)
    return WikiWorkspace(
        data_store=WikiDataStore(root / data_dir),
        vault_root=root / vault_dir,
    )
