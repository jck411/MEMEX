"""Direct-provider model profiles for source extraction."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class ExtractionModelProfile:
    profile_id: str
    provider: str
    model: str
    env_key: str
    strengths: tuple[str, ...]
    input_formats: tuple[str, ...]
    structured_output: str
    parameter_notes: tuple[str, ...]
    docs: tuple[str, ...]
    enabled: bool = True
    schema_strict: bool = True
    schema_name: str = "memex_wiki_prep_extraction"


@dataclass(frozen=True)
class ModelProfileReadiness:
    profile: ExtractionModelProfile
    configured: bool
    missing_env_key: str


@dataclass(frozen=True)
class ExtractionFormatRoute:
    format_family: str
    profile_id: str
    source_types: tuple[str, ...]
    reason: str


OPENAI_GPT55_EXTRACTION = ExtractionModelProfile(
    profile_id="openai:gpt-5.5",
    provider="openai",
    model="gpt-5.5",
    env_key="OPENAI_API_KEY",
    strengths=(
        "structured extraction",
        "PDF text plus page-image analysis",
        "broad document and spreadsheet ingestion",
    ),
    input_formats=(
        "PDF visual+text",
        "images",
        "docx/pptx/txt/code text",
        "xlsx/csv/tsv spreadsheet augmentation",
    ),
    structured_output="Responses API text.format json_schema",
    parameter_notes=(
        "supports reasoning.effort",
        "supports text.verbosity",
        "supports image_detail",
    ),
    docs=(
        "https://developers.openai.com/api/docs/guides/latest-model",
        "https://developers.openai.com/api/docs/guides/file-inputs",
        "https://developers.openai.com/api/docs/guides/structured-outputs",
    ),
)


GOOGLE_GEMINI35_FLASH_EXTRACTION = ExtractionModelProfile(
    profile_id="google:gemini-3.5-flash",
    provider="google",
    model="gemini-3.5-flash",
    env_key="GEMINI_API_KEY",
    strengths=(
        "structured extraction",
        "PDF document analysis",
        "image understanding",
        "fast multimodal source inspection",
    ),
    input_formats=(
        "PDF documents",
        "JPEG/PNG/GIF/WebP images",
        "text files",
    ),
    structured_output="Gemini generateContent responseMimeType responseJsonSchema",
    parameter_notes=(
        "supports inline PDF data",
        "supports inline image data",
        "uses generationConfig.responseMimeType and responseJsonSchema",
    ),
    docs=(
        "https://ai.google.dev/gemini-api/docs/api-overview",
        "https://ai.google.dev/gemini-api/docs/document-processing",
        "https://ai.google.dev/gemini-api/docs/image-understanding",
        "https://ai.google.dev/gemini-api/docs/structured-output",
    ),
)


ANTHROPIC_SONNET46_EXTRACTION = ExtractionModelProfile(
    profile_id="anthropic:claude-sonnet-4-6",
    provider="anthropic",
    model="claude-sonnet-4-6",
    env_key="ANTHROPIC_API_KEY",
    strengths=(
        "structured extraction",
        "PDF document analysis",
        "fast high-quality vision over source material",
    ),
    input_formats=(
        "PDF visual+text",
        "JPEG/PNG/GIF/WebP images",
        "text files through Files API",
    ),
    structured_output="Messages API forced tool input_schema",
    parameter_notes=(
        "supports extended and adaptive thinking",
        "use effort for thinking depth",
        "do not rely on OpenAI-style response_format",
    ),
    docs=(
        "https://platform.claude.com/docs/en/about-claude/models/overview",
        "https://platform.claude.com/docs/en/build-with-claude/pdf-support",
        "https://platform.claude.com/docs/en/build-with-claude/structured-outputs",
    ),
)


DEFAULT_EXTRACTION_MODEL_PROFILES = (
    ANTHROPIC_SONNET46_EXTRACTION,
    OPENAI_GPT55_EXTRACTION,
    GOOGLE_GEMINI35_FLASH_EXTRACTION,
)

DEFAULT_EXTRACTION_PROFILE_ID = ANTHROPIC_SONNET46_EXTRACTION.profile_id


DEFAULT_EXTRACTION_FORMAT_ROUTES = (
    ExtractionFormatRoute(
        format_family="pdf",
        profile_id=ANTHROPIC_SONNET46_EXTRACTION.profile_id,
        source_types=("pdf",),
        reason="Sonnet 4.6 is the default visual document extractor.",
    ),
    ExtractionFormatRoute(
        format_family="image",
        profile_id=ANTHROPIC_SONNET46_EXTRACTION.profile_id,
        source_types=("image", "jpg", "png", "gif", "webp", "tiff"),
        reason="Sonnet 4.6 is the default image and scanned-source extractor.",
    ),
    ExtractionFormatRoute(
        format_family="text",
        profile_id=ANTHROPIC_SONNET46_EXTRACTION.profile_id,
        source_types=("text", "markdown", "code", "json", "html", "xml"),
        reason="Sonnet 4.6 is the default text extractor.",
    ),
    ExtractionFormatRoute(
        format_family="office",
        profile_id=ANTHROPIC_SONNET46_EXTRACTION.profile_id,
        source_types=("docx", "pptx"),
        reason="Sonnet 4.6 is the default office document extractor.",
    ),
    ExtractionFormatRoute(
        format_family="spreadsheet",
        profile_id=ANTHROPIC_SONNET46_EXTRACTION.profile_id,
        source_types=("xlsx", "csv", "tsv"),
        reason="Sonnet 4.6 is the default spreadsheet extractor.",
    ),
)


def load_env_file(path: str | Path) -> dict[str, str]:
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name:
            values[name] = value
    return values


def merged_env(env_file: str | Path = ".env") -> dict[str, str]:
    values = dict(os.environ)
    values.update(load_env_file(env_file))
    return values


def model_profile_readiness(
    profile: ExtractionModelProfile,
    env: Mapping[str, str],
) -> ModelProfileReadiness:
    configured = bool(env.get(profile.env_key))
    return ModelProfileReadiness(
        profile=profile,
        configured=configured,
        missing_env_key="" if configured else profile.env_key,
    )


def enabled_extraction_model_profiles(
    profiles: tuple[ExtractionModelProfile, ...] = DEFAULT_EXTRACTION_MODEL_PROFILES,
) -> tuple[ExtractionModelProfile, ...]:
    return tuple(profile for profile in profiles if profile.enabled)


def extraction_profile_by_id(
    profile_id: str,
    profiles: tuple[ExtractionModelProfile, ...] = DEFAULT_EXTRACTION_MODEL_PROFILES,
) -> ExtractionModelProfile:
    for profile in profiles:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(f"unknown extraction model profile {profile_id!r}")


def extraction_routes_for_profile(
    profile_id: str,
    routes: tuple[ExtractionFormatRoute, ...] = DEFAULT_EXTRACTION_FORMAT_ROUTES,
) -> tuple[ExtractionFormatRoute, ...]:
    return tuple(route for route in routes if route.profile_id == profile_id)


def extraction_route_for_source_type(
    source_type: str,
    routes: tuple[ExtractionFormatRoute, ...] = DEFAULT_EXTRACTION_FORMAT_ROUTES,
) -> ExtractionFormatRoute | None:
    normalized = _normalize_source_type(source_type)
    for route in routes:
        if normalized in route.source_types:
            return route
    return None


def extraction_profile_for_source_type(
    source_type: str,
    profiles: tuple[ExtractionModelProfile, ...] = DEFAULT_EXTRACTION_MODEL_PROFILES,
    routes: tuple[ExtractionFormatRoute, ...] = DEFAULT_EXTRACTION_FORMAT_ROUTES,
) -> ExtractionModelProfile | None:
    route = extraction_route_for_source_type(source_type, routes)
    if route is None:
        return None
    return extraction_profile_by_id(route.profile_id, profiles)


def extraction_model_readiness(
    env: Mapping[str, str] | None = None,
) -> tuple[ModelProfileReadiness, ...]:
    values = os.environ if env is None else env
    return tuple(
        model_profile_readiness(profile, values) for profile in DEFAULT_EXTRACTION_MODEL_PROFILES
    )


def _normalize_source_type(source_type: str) -> str:
    value = source_type.strip().lower().lstrip(".")
    aliases = {
        "jpeg": "jpg",
        "md": "markdown",
        "markdown": "markdown",
        "txt": "text",
        "plain": "text",
        "py": "code",
        "js": "code",
        "ts": "code",
        "tsx": "code",
        "jsx": "code",
        "htm": "html",
        "xls": "xlsx",
        "doc": "docx",
        "ppt": "pptx",
        "tif": "tiff",
    }
    return aliases.get(value, value)
