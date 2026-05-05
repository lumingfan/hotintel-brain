"""Brain runtime configuration loaded from environment / .env file."""

from __future__ import annotations

import os
import sys
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All Brain runtime config.

    All values default to safe placeholders so that the service can boot and
    `pytest` can run without any real LLM or Langfuse credentials. Endpoints
    that actually hit external services check the relevant `*_api_key` /
    `*_host` fields and return clear errors if unset.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ----- Brain core -----
    brain_default_model: str = Field(default="gpt-4o-mini")
    brain_default_layer: str = Field(default="L1")
    brain_log_level: str = Field(default="INFO")
    brain_llm_timeout_seconds: int = Field(default=20)
    brain_embed_model_path: str = Field(default="models/bge-m3")
    brain_rerank_model_path: str = Field(default="models/bge-reranker-v2-m3")
    brain_device: str = Field(default="auto")
    brain_rabbitmq_url: str = Field(default="")
    brain_es_index_name: str = Field(default="hotspot_search")

    # ----- LLM providers (ADR 0006: V1 = GPT + Claude) -----
    openai_api_key: str = Field(default="")
    openai_base_url: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # ----- Langfuse -----
    langfuse_host: str = Field(default="http://localhost:3000")
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_prompt_fetch_enabled: bool = Field(default=False)

    # ----- Elasticsearch (V2 起用) -----
    brain_es_url: str = Field(default="")
    brain_es_user: str = Field(default="")
    brain_es_pass: str = Field(default="")

    # ----- Derived helpers -----
    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def anthropic_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Tests can monkeypatch env then call cache_clear."""
    env_file = os.environ.get("BRAIN_ENV_FILE")
    if env_file is None:
        env_file = "" if "pytest" in sys.modules else ".env"
    if env_file == "":
        return Settings(_env_file=None)
    return Settings(_env_file=env_file)
