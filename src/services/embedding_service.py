"""Dedicated embedding service for MemoryMesh semantic memory retrieval.

Handles embedding generation via Ollama (nomic-embed-text by default),
vector dimension validation, consistent canonical text representation,
resilient error handling, and timeout control.
"""

from __future__ import annotations
import logging
import math
from typing import Optional, List, Tuple, Dict, Any
import ollama as ollama_lib

from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Base exception for embedding operations."""
    pass


class EmbeddingUnavailableError(EmbeddingError):
    """Raised when the embedding model or server is unreachable."""
    pass


class EmbeddingTimeoutError(EmbeddingError):
    """Raised when embedding generation exceeds the configured timeout."""
    pass


class EmbeddingDimensionMismatchError(EmbeddingError):
    """Raised when the returned embedding vector dimension differs from configuration."""
    pass


def format_fact_for_embedding(subject: str, predicate: str, value: str) -> str:
    """Produce a deterministic canonical text representation of a Fact for embedding."""
    sub = (subject or "").strip()
    pred = (predicate or "").strip()
    val = (value or "").strip()
    return f"{sub} {pred} {val}".strip()


def format_query_for_embedding(query: str) -> str:
    """Normalize and format user query text for embedding generation."""
    return (query or "").strip()


def check_embedding_health() -> Dict[str, Any]:
    """Check if the embedding server is available and model produces valid vectors.

    Returns:
        dict with keys: available (bool), model (str), dimension (int), error (Optional[str])
    """
    model = settings.EMBEDDING_MODEL
    expected_dim = settings.EMBEDDING_DIM
    try:
        client = ollama_lib.Client(host=settings.OLLAMA_HOST)
        models_resp = client.list()
        model_names: List[str] = []
        if hasattr(models_resp, "models"):
            model_names = [m.model for m in models_resp.models]
        elif isinstance(models_resp, dict) and "models" in models_resp:
            model_names = [m.get("model", m.get("name", "")) for m in models_resp["models"]]

        if not any(model in name for name in model_names):
            return {
                "available": False,
                "model": model,
                "dimension": expected_dim,
                "error": f"Model '{model}' not found in Ollama. Pull with: ollama pull {model}",
            }

        # Probe embedding generation
        probe_resp = client.embeddings(model=model, prompt="probe")
        vec = probe_resp.get("embedding", [])
        if len(vec) != expected_dim:
            return {
                "available": False,
                "model": model,
                "dimension": len(vec),
                "error": f"Model '{model}' produced dimension {len(vec)}, expected {expected_dim}",
            }

        return {
            "available": True,
            "model": model,
            "dimension": expected_dim,
            "error": None,
        }
    except Exception as e:
        return {
            "available": False,
            "model": model,
            "dimension": expected_dim,
            "error": f"Ollama embedding service error at {settings.OLLAMA_HOST}: {e}",
        }


def get_embedding(
    text: str,
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> List[float]:
    """Generate an embedding vector from text using Ollama nomic-embed-text.

    Args:
        text: Input string to embed.
        model: Optional model override (defaults to settings.EMBEDDING_MODEL).
        timeout: Optional timeout in seconds (defaults to settings.EMBEDDING_TIMEOUT).

    Returns:
        List of floats of length settings.EMBEDDING_DIM.

    Raises:
        ValueError: If input text is empty.
        EmbeddingUnavailableError: If Ollama cannot be reached.
        EmbeddingTimeoutError: If generation times out.
        EmbeddingDimensionMismatchError: If vector dimension does not match config.
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty or whitespace-only text.")

    target_model = model or settings.EMBEDDING_MODEL
    expected_dim = settings.EMBEDDING_DIM
    timeout_sec = timeout or settings.EMBEDDING_TIMEOUT

    import concurrent.futures

    def _sync_call() -> List[float]:
        client = ollama_lib.Client(host=settings.OLLAMA_HOST)
        resp = client.embeddings(model=target_model, prompt=text)
        return resp.get("embedding", [])

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_sync_call)
            vec = future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        logger.error(f"Embedding generation timed out after {timeout_sec}s for model '{target_model}'")
        raise EmbeddingTimeoutError(f"Embedding generation timed out after {timeout_sec}s")
    except Exception as e:
        logger.error(f"Failed to generate embedding with model '{target_model}': {e}")
        raise EmbeddingUnavailableError(f"Embedding service unavailable: {e}")

    if not vec or not isinstance(vec, list):
        raise EmbeddingError(f"Malformed embedding response from Ollama: {type(vec)}")

    actual_dim = len(vec)
    if actual_dim != expected_dim:
        raise EmbeddingDimensionMismatchError(
            f"Embedding dimension mismatch: model '{target_model}' produced {actual_dim} dimensions, "
            f"expected {expected_dim}"
        )

    # Verify numerical integrity
    for val in vec:
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            raise EmbeddingError("Embedding vector contains non-numerical, NaN, or infinite values.")

    return [float(v) for v in vec]


def generate_embedding_safe(text: str) -> Tuple[Optional[List[float]], Optional[str]]:
    """Safe wrapper around get_embedding that never raises, returning (embedding, error)."""
    try:
        vec = get_embedding(text)
        return vec, None
    except Exception as e:
        logger.warning(f"Embedding generation safe fallback triggered: {e}")
        return None, str(e)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two float vectors.

    Returns float in range [-1.0, 1.0].
    """
    if len(vec1) != len(vec2) or len(vec1) == 0:
        return 0.0

    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(vec1, vec2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b

    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0

    sim = dot / (math.sqrt(norm1) * math.sqrt(norm2))
    # Clamp for numerical stability
    return max(-1.0, min(1.0, sim))


def cosine_distance(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine distance (1.0 - cosine_similarity). Range [0.0, 2.0]."""
    return 1.0 - cosine_similarity(vec1, vec2)
