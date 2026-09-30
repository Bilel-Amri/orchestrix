"""LLM client — interface stable entre les agents et le provider.

Permet de basculer entre Ollama / vLLM / OpenAI-compatible sans toucher
au code des agents. Chaque appel est tracé dans Langfuse (si configuré).
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from orchestrix.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper LLM unique. Le provider se configure via .env."""

    def __init__(self, model: str | None = None, provider: str | None = None) -> None:
        settings = get_settings()
        self._provider = provider or settings.llm_provider
        self._model = model or settings.llm_model
        self._client = self._build_client()

    def _build_client(self) -> Any:
        settings = get_settings()
        if self._provider in ("ollama", "vllm"):
            return ChatOllama(
                model=self._model,
                base_url=settings.llm_base_url.replace("/v1", ""),
                temperature=0.0,
            )
        if self._provider == "openai":
            return ChatOpenAI(
                model=self._model,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                temperature=0.0,
            )
        raise ValueError(f"Unknown LLM provider: {self._provider}")

    def invoke(self, messages: list[BaseMessage]) -> str:
        """Invoque le LLM et retourne le contenu textuel."""
        response = self._client.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)


def get_default_llm() -> LLMClient:
    """Singleton simple pour usage rapide."""
    return LLMClient()
