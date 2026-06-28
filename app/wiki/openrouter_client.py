"""Small OpenRouter chat completion helpers."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEEPSEEK_V4_PRO_MODEL = "deepseek/deepseek-v4-pro"
MAX_OPENROUTER_ERROR_MESSAGE = 1_200


def post_openrouter_chat_completion(
    api_key: str,
    body: Mapping[str, Any],
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: int = 120,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    request = Request(
        OPENROUTER_CHAT_COMPLETIONS_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": "MEMEX",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=timeout) as response:
            raw_payload = response.read()
    except HTTPError as error:
        raise RuntimeError(
            f"OpenRouter returned HTTP {error.code}: {_http_error_message(error)}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"OpenRouter request failed: {error.reason}") from error

    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"OpenRouter response was not JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("OpenRouter response was not a JSON object")
    api_error = _api_error_message(payload)
    if api_error:
        raise RuntimeError(f"OpenRouter returned an error: {api_error}")
    return payload


def chat_completion_text(data: Mapping[str, Any], *, task: str) -> str:
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            f"OpenRouter {task} response did not contain a message: {error}"
        ) from error
    if isinstance(choice, Mapping) and choice.get("finish_reason") == "length":
        raise ValueError(f"OpenRouter {task} response reached max_tokens")
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    raise ValueError(f"OpenRouter {task} response did not contain output text")


def strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _http_error_message(error: HTTPError) -> str:
    body = error.read().decode("utf-8", errors="replace").strip()
    if not body:
        return _clip_error(error.reason)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return _clip_error(body)
    if isinstance(payload, Mapping):
        return _api_error_message(payload) or _clip_error(
            json.dumps(payload, ensure_ascii=True)
        )
    return _clip_error(body)


def _api_error_message(payload: Mapping[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, Mapping):
        message = _string_value(error.get("message")) or _string_value(error.get("detail"))
        code = _string_value(error.get("code")) or _string_value(error.get("type"))
        metadata = error.get("metadata")
        metadata_message = _metadata_message(metadata)
        parts = [part for part in (code, message, metadata_message) if part]
        if parts:
            return _clip_error("; ".join(parts))
        return _clip_error(json.dumps(error, ensure_ascii=True))
    if isinstance(error, str) and error.strip():
        return _clip_error(error)
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return _clip_error(message)
    return ""


def _metadata_message(metadata: object) -> str:
    if isinstance(metadata, str):
        return metadata.strip()
    if not isinstance(metadata, Mapping):
        return ""
    for key in ("reason", "message", "details", "raw", "provider_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return f"{key}: {value.strip()}"
    return ""


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _clip_error(message: object) -> str:
    text = " ".join(str(message).split())
    if len(text) <= MAX_OPENROUTER_ERROR_MESSAGE:
        return text
    return text[: MAX_OPENROUTER_ERROR_MESSAGE - 3].rstrip() + "..."
