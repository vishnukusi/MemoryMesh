"""Configuration settings for MemoryMesh.

Loads environment variables with fallbacks for local development.
"""

from __future__ import annotations
import os
from typing import List
from pathlib import Path
from dotenv import load_dotenv

# Only load .env if it exists in the project root to prevent climbing into parent/home dirs
_project_root = Path(__file__).resolve().parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    try:
        load_dotenv(dotenv_path=_env_file)
    except Exception:
        pass


class Settings:
    """Application settings loaded from environment or defaults."""

    # FalkorDB / Redis connection
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))

    # Ollama local LLM
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    MODEL_TIMEOUT: int = int(os.getenv("MODEL_TIMEOUT", "60"))
    MAX_CONCURRENT_INFERENCE: int = int(os.getenv("MAX_CONCURRENT_INFERENCE", "2"))

    # Multi-tenant graph settings
    GRAPH_PREFIX: str = os.getenv("GRAPH_PREFIX", "memorymesh_")
    ALLOWED_TENANTS: List[str] = ["tenant_alpha", "tenant_beta"]

    # Security & Authentication
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    DEV_MODE: bool = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
    IDEMPOTENCY_TIMEOUT_SECONDS: int = int(os.getenv("IDEMPOTENCY_TIMEOUT_SECONDS", "120"))
    API_KEY_HEADER: str = "X-API-Key"
    TENANT_HEADER: str = "X-Tenant-ID"
    # Admin master key (optional, grants access across tenants if provided)
    MASTER_API_KEY: str = os.getenv("MASTER_API_KEY", "")
    # Tenant-specific API keys: {"tenant_alpha": "alpha-secret", "tenant_beta": "beta-secret"}
    TENANT_KEYS: dict[str, str] = {
        "tenant_alpha": os.getenv("API_KEY_TENANT_ALPHA", "dev-alpha-key"),
        "tenant_beta": os.getenv("API_KEY_TENANT_BETA", "dev-beta-key"),
    }

    # CORS settings (avoid wildcard with credentials)
    CORS_ALLOWED_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:8501,http://127.0.0.1:8501,http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]

    def validate_production_config(self) -> None:
        """Enforce strict production security constraints.
        
        Raises RuntimeError if production is configured unsafely.
        """
        if self.ENVIRONMENT in ("production", "prod"):
            if self.DEV_MODE:
                raise RuntimeError("Production security violation: DEV_MODE cannot be enabled in production.")
            if not self.AUTH_ENABLED:
                raise RuntimeError("Production security violation: AUTH_ENABLED must be True in production.")
            for tenant, key in self.TENANT_KEYS.items():
                if not key or key in ("dev-alpha-key", "dev-beta-key"):
                    raise RuntimeError(
                        f"Production security violation: Tenant '{tenant}' must have a secure, "
                        f"non-default API key configured in production."
                    )
            for origin in self.CORS_ALLOWED_ORIGINS:
                if origin == "*":
                    raise RuntimeError("Production security violation: Wildcard CORS origin not allowed in production.")

    def get_graph_name(self, tenant_id: str) -> str:
        """Return the isolated FalkorDB graph name for a valid tenant.
        
        Raises ValueError if the tenant is not recognized or allowed.
        """
        if tenant_id not in self.ALLOWED_TENANTS:
            raise ValueError(f"Invalid or unauthorized tenant: '{tenant_id}'")
        return f"{self.GRAPH_PREFIX}{tenant_id}"


settings = Settings()
