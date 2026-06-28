"""Small OpenRouter chat completion helpers."""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEEPSEEK_V4_PRO_MODEL = "deepseek/deepseek-v4-pro"


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
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OpenRouter response was not a JSON object")
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
