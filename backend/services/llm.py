"""The one place that knows which model runs the review.

ChatOllama talks to a local Ollama server. reasoning=False switches thinking
off for models that support it (Qwen 3.x); num_ctx and num_predict are set
explicitly because Ollama's defaults (2048 and 128) are far too small for a
diff review; validate_model_on_init is off so the API can boot while Ollama
is down, and /api/status reports that instead."""

from typing import Any, Dict, Optional

import httpx
from langchain_ollama import ChatOllama

from config.logging import get_logger
from config.settings import Settings

logger = get_logger(__name__)


def build_chat_model(settings: Settings, model: Optional[str] = None, keep_alive: Optional[str] = None) -> ChatOllama:
    return ChatOllama(
        model=model or settings.OLLAMA_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        num_ctx=settings.OLLAMA_NUM_CTX,
        num_predict=settings.OLLAMA_NUM_PREDICT,
        temperature=settings.OLLAMA_TEMPERATURE,
        keep_alive=keep_alive or settings.OLLAMA_KEEP_ALIVE,
        reasoning=False,
        validate_model_on_init=False,
        client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
    )


def build_cross_model(settings: Settings) -> Optional[ChatOllama]:
    """The cross-examining model, or None when none is configured. Same
    loopback server, so the local claim is unchanged."""
    if not settings.CROSS_EXAMINE_MODEL:
        return None
    return build_chat_model(settings, model=settings.CROSS_EXAMINE_MODEL, keep_alive=settings.CROSS_EXAMINE_KEEP_ALIVE)


async def unload_model(settings: Settings, model: str) -> bool:
    """Ask Ollama to drop a model now rather than at the end of its keep_alive,
    so a machine that cannot hold the reviewer and the cross-examiner together
    can run them one after the other. Same loopback server, no generation; a
    failure is logged and ignored because an unload must never fail a review."""
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{base}/api/generate", json={"model": model, "keep_alive": 0})
            resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001 - reachability and HTTP errors alike; never CancelledError
        logger.warning("could not unload model", model=model, error=type(e).__name__)
        return False


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
            if settings.CROSS_EXAMINE_MODEL:
                out["cross_model"] = settings.CROSS_EXAMINE_MODEL
                out["cross_model_present"] = (settings.CROSS_EXAMINE_MODEL in names
                                              or f"{settings.CROSS_EXAMINE_MODEL}:latest" in names)
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
