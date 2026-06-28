"""High-level source extraction workflow for direct-provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import urlopen

from .anthropic_extraction import AnthropicSourceExtractor
from .extraction_inputs import ExtractionInput, extraction_input_from_path
from .extraction_packets import ExtractionPacketError
from .google_extraction import GoogleSourceExtractor
from .model_profiles import (
    DEFAULT_EXTRACTION_PROFILE_ID,
    extraction_profile_by_id,
    extraction_profile_for_source_type,
)
from .openai_extraction import OpenAISourceExtractor
from .records import SourceRecord
from .workflows import WikiWorkspace


@dataclass(frozen=True)
class SourceExtractionJob:
    source_id: str
    path: str | Path
    title: str = ""
    source_type: str = ""
    model_spec: str = ""
    source_kind: str = "local_path"
    mime_type: str = ""
    allow_duplicate: bool = False
    operator_instructions: str = ""


@dataclass(frozen=True)
class SourceExtractionWorkflowResult:
    source: SourceRecord
    model_spec: str
    usage: Mapping[str, Any]
    duplicate_source_id: str = ""
    sha256: str = ""

    @property
    def duplicate(self) -> bool:
        return bool(self.duplicate_source_id)

    @property
    def created(self) -> bool:
        return not self.duplicate


def extract_source_to_workspace(
    workspace: WikiWorkspace,
    job: SourceExtractionJob,
    env: Mapping[str, str],
    *,
    opener: Callable[..., Any] = urlopen,
) -> SourceExtractionWorkflowResult:
    asset_store = workspace.source_assets()
    staged_asset = asset_store.stage_file(
        job.source_id,
        job.path,
        source_kind=job.source_kind,
        mime_type=job.mime_type,
    )
    try:
        duplicate_source_id = (
            ""
            if job.allow_duplicate
            else asset_store.duplicate_source_id_for_sha256(staged_asset.sha256)
        )
        if duplicate_source_id:
            source = workspace.data_store.load_source(duplicate_source_id)
            staged_asset.discard()
            return SourceExtractionWorkflowResult(
                source=source,
                model_spec=job.model_spec,
                usage={},
                duplicate_source_id=duplicate_source_id,
                sha256=staged_asset.sha256,
            )
        if _source_exists(workspace, job.source_id):
            raise ValueError(f"source {job.source_id!r} already exists; choose a new source id")

        source_input = extraction_input_from_path(
            staged_asset.original_path,
            job.source_id,
            title=job.title,
            source_type=job.source_type,
            operator_instructions=job.operator_instructions,
        )
        model_spec = job.model_spec or default_model_spec_for_source_type(source_input.source_type)
        provider, model = parse_extraction_model_spec(model_spec)
        result = _extract_with_provider(
            provider,
            model,
            source_input,
            env,
            opener,
        )
        workspace.save_source(result.source)
        run = result.packet.get("run", {})
        staged_asset.commit(
            extraction_provider=provider,
            extraction_model=model,
            extracted_at=run.get("extracted_at", "") if isinstance(run, Mapping) else "",
            usage=result.usage,
        )
        return SourceExtractionWorkflowResult(
            source=result.source,
            model_spec=model_spec,
            usage=result.usage,
            sha256=staged_asset.sha256,
        )
    except Exception:
        staged_asset.discard()
        raise


def default_model_spec_for_source_type(source_type: str) -> str:
    profile = extraction_profile_for_source_type(source_type)
    return profile.profile_id if profile else DEFAULT_EXTRACTION_PROFILE_ID


def parse_extraction_model_spec(model_spec: str) -> tuple[str, str]:
    if ":" not in model_spec:
        profile = extraction_profile_by_id(model_spec)
        return profile.provider, profile.model
    provider, model = model_spec.split(":", 1)
    return provider, model


def _extract_with_provider(
    provider: str,
    model: str,
    source_input: ExtractionInput,
    env: Mapping[str, str],
    opener: Callable[..., Any],
):
    if provider == "anthropic":
        return AnthropicSourceExtractor(
            api_key=env.get("ANTHROPIC_API_KEY", ""),
            model=model,
            opener=opener,
        ).extract(source_input)
    if provider == "openai":
        return OpenAISourceExtractor(
            api_key=env.get("OPENAI_API_KEY", ""),
            model=model,
            opener=opener,
        ).extract(source_input)
    if provider == "google":
        return GoogleSourceExtractor(
            api_key=env.get("GEMINI_API_KEY", ""),
            model=model,
            opener=opener,
        ).extract(source_input)
    raise ExtractionPacketError(f"unsupported extraction provider {provider!r}")


def _source_exists(workspace: WikiWorkspace, source_id: str) -> bool:
    try:
        workspace.data_store.load_source(source_id)
    except FileNotFoundError:
        return False
    return True
