"""Ollama model service for MemoryMesh.

Handles all LLM interactions with proper timeout handling,
error recovery, and structured JSON output parsing.
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from typing import Optional

import ollama as ollama_lib

from src.config import settings

logger = logging.getLogger(__name__)

# Semaphore to limit concurrent inference calls
_inference_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _inference_semaphore
    if _inference_semaphore is None:
        _inference_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_INFERENCE)
    return _inference_semaphore


def check_ollama_health() -> dict:
    """Check if Ollama is reachable and the configured model is available.

    Returns:
        dict with keys: available (bool), model (str), error (str|None)
    """
    try:
        client = ollama_lib.Client(host=settings.OLLAMA_HOST)
        models = client.list()
        model_names = []
        if hasattr(models, "models"):
            model_names = [m.model for m in models.models]
        elif isinstance(models, dict) and "models" in models:
            model_names = [m.get("model", m.get("name", "")) for m in models["models"]]

        # Check if our configured model is available
        target = settings.OLLAMA_MODEL
        found = any(target in name for name in model_names)
        return {
            "available": True,
            "model": target,
            "model_loaded": found,
            "available_models": model_names[:10],
            "error": None if found else f"Model '{target}' not found. Run: ollama pull {target}",
        }
    except Exception as e:
        return {
            "available": False,
            "model": settings.OLLAMA_MODEL,
            "model_loaded": False,
            "available_models": [],
            "error": f"Ollama not reachable at {settings.OLLAMA_HOST}. "
                     f"Install from https://ollama.ai and run: ollama serve. Error: {e}",
        }


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from model output, handling markdown code blocks and extra text."""
    if not text:
        return None

    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in code blocks
    patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

    # Last resort: find first { to last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    return None


def _sync_generate(system_prompt: str, user_prompt: str,
                   temperature: float = 0.3) -> str:
    """Synchronous Ollama generate call."""
    client = ollama_lib.Client(host=settings.OLLAMA_HOST)
    response = client.generate(
        model=settings.OLLAMA_MODEL,
        system=system_prompt,
        prompt=user_prompt,
        options={
            "temperature": temperature,
            "num_predict": 2048,
        },
        # Tell Qwen3 to NOT use thinking/reasoning (for structured output)
        # by appending /no_think flag in the prompt
    )
    return response.get("response", "") if isinstance(response, dict) else getattr(response, "response", "")


async def generate_text(system_prompt: str, user_prompt: str,
                        temperature: float = 0.3) -> str:
    """Generate text from the local model with concurrency control.

    Runs the synchronous Ollama call in a thread to avoid blocking
    the FastAPI event loop.
    """
    sem = _get_semaphore()
    async with sem:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_sync_generate, system_prompt, user_prompt, temperature),
                timeout=settings.MODEL_TIMEOUT,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Model inference timed out after {settings.MODEL_TIMEOUT}s")
            raise RuntimeError(f"Model inference timed out after {settings.MODEL_TIMEOUT} seconds")
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            raise


async def generate_json(system_prompt: str, user_prompt: str,
                        temperature: float = 0.1) -> Optional[dict]:
    """Generate structured JSON output from the model.

    Lower temperature for more reliable JSON output.
    Parses and validates the response.
    """
    # Append instruction for JSON output
    enhanced_prompt = user_prompt + "\n\nRespond ONLY with valid JSON. No explanation, no markdown, just the JSON object."

    raw = await generate_text(system_prompt, enhanced_prompt, temperature)

    parsed = _extract_json(raw)
    if parsed is None:
        logger.warning(f"Failed to parse JSON from model output: {raw[:200]}")
    return parsed


def sync_check_ollama() -> bool:
    """Quick synchronous check if Ollama is available."""
    try:
        client = ollama_lib.Client(host=settings.OLLAMA_HOST)
        client.list()
        return True
    except Exception:
        return False
