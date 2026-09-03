"""The one place that knows which model runs the review.

ChatOllama talks to a local Ollama server. reasoning=False switches thinking
off for models that support it (Qwen 3.x); num_ctx and num_predict are set
explicitly because Ollama's defaults (2048 and 128) are far too small for a
diff review; validate_model_on_init is off so the API can boot while Ollama
is down, and /api/status reports that instead."""

from typing import Any, Dict

import httpx
from langchain_ollama import ChatOllama

from config.settings import Settings


def build_chat_model(settings: Settings) -> ChatOllama:
    return ChatOllama(
        model=settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        num_ctx=settings.OLLAMA_NUM_CTX,
        num_predict=settings.OLLAMA_NUM_PREDICT,
        temperature=settings.OLLAMA_TEMPERATURE,
        keep_alive=settings.OLLAMA_KEEP_ALIVE,
        reasoning=False,
        validate_model_on_init=False,
        client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
    )


async def ollama_health(settings: Settings) -> Dict[str, Any]:
    """Reachability, whether the configured model is pulled, and what is
    loaded. Never runs a generation."""
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    out: Dict[str, Any] = {"reachable": False, "model": settings.OLLAMA_MODEL, "model_present": False, "loaded": []}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            tags = await client.get(f"{base}/api/tags")
            tags.raise_for_status()
            names = {m.get("name") for m in tags.json().get("models", [])}
            out["reachable"] = True
            out["model_present"] = settings.OLLAMA_MODEL in names or f"{settings.OLLAMA_MODEL}:latest" in names
            ps = await client.get(f"{base}/api/ps")
            if ps.status_code == 200:
                out["loaded"] = [
                    {"name": m.get("name"), "size_vram": m.get("size_vram"), "context_length": m.get("context_length")}
                    for m in ps.json().get("models", [])
                ]
    except Exception as e:  # reachability is the point; any failure means not reachable
        out["error"] = type(e).__name__
    return out
