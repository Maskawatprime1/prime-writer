"""Minimal Ollama client shared by the writer and the clipper."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not OLLAMA_URL.startswith("http"):
    OLLAMA_URL = "http://" + OLLAMA_URL

TIMEOUT = httpx.Timeout(600.0, connect=5.0)
# trust_env=False: never route local calls through HTTP(S)_PROXY (e.g. Clash).
_client = httpx.Client(trust_env=False, timeout=TIMEOUT)


class OllamaError(RuntimeError):
    pass


def _post(path: str, payload: dict) -> dict:
    try:
        r = _client.post(f"{OLLAMA_URL}{path}", json=payload)
    except httpx.HTTPError as e:
        raise OllamaError(f"Cannot reach Ollama at {OLLAMA_URL}. Is it running? ({e})") from e
    if r.status_code != 200:
        raise OllamaError(f"Ollama error {r.status_code}: {r.text[:300]}")
    return r.json()


def is_up() -> bool:
    try:
        return _client.get(f"{OLLAMA_URL}/api/version", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


def list_models() -> list[str]:
    try:
        r = _client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    except httpx.HTTPError:
        return []


def loaded_models() -> list[str]:
    try:
        r = _client.get(f"{OLLAMA_URL}/api/ps", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except httpx.HTTPError:
        return []


def unload_all() -> list[str]:
    """Free VRAM: ask Ollama to evict every loaded model."""
    names = loaded_models()
    for name in names:
        try:
            _post("/api/generate", {"model": name, "keep_alive": 0})
        except OllamaError:
            pass
    return names


def chat(
    model: str,
    system: str,
    user: str,
    *,
    schema: dict | None = None,
    temperature: float = 0.3,
    num_ctx: int = 4096,
    keep_alive: str | int = "10m",
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if schema is not None:
        payload["format"] = schema
    if "qwen3" in model or "deepseek-r1" in model:
        payload["think"] = False  # skip chain-of-thought: faster, cleaner output
    data = _post("/api/chat", payload)
    return data.get("message", {}).get("content", "").strip()


def chat_json(model: str, system: str, user: str, schema: dict, **kw) -> Any:
    raw = chat(model, system, user, schema=schema, temperature=kw.pop("temperature", 0.1), **kw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise OllamaError(f"Model did not return valid JSON: {raw[:200]}")
