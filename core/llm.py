"""Anthropic API client -- urllib only, no dependencies.

Supports both sk-ant API keys and OAuth JWT tokens.
"""

import json
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


def _build_headers(api_key):
    """Build request headers. Detects key type for auth header."""
    headers = {
        "content-type": "application/json",
        "anthropic-version": API_VERSION,
    }
    if api_key.startswith("sk-ant-"):
        headers["x-api-key"] = api_key
    else:
        headers["authorization"] = "Bearer " + api_key
    return headers


def chat(api_key, model, messages, system=None, max_tokens=1024):
    """Send a chat completion request. Returns assistant text.

    Args:
        api_key: sk-ant-* key or OAuth JWT
        model: model ID string
        messages: list of {"role": "user"|"assistant", "content": "..."}
        system: optional system prompt string
        max_tokens: max response tokens

    Returns:
        str: assistant response text

    Raises:
        LLMError on API failure
    """
    body = {
        "model": model,
        "max_tokens": int(max_tokens),
        "messages": messages,
    }
    if system:
        body["system"] = system

    data = json.dumps(body).encode()
    req = urllib.request.Request(API_URL, data=data, headers=_build_headers(api_key))

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise LLMError(f"API {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"Connection failed: {e.reason}") from e

    # Extract text from content blocks
    for block in result.get("content", []):
        if block.get("type") == "text":
            return block["text"]

    return ""


class LLMError(Exception):
    """Raised when the LLM API call fails."""
