"""LLM client factory.

All LLM calls in this project go through the local Ollama OpenAI-compatible
endpoint. The default model is `qwen3:1.7b`; override it with OLLAMA_MODEL in
.env if a different local model is needed.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from email_agent.config import CONFIG


@lru_cache(maxsize=4)
def get_chat_model(
    temperature: float = 0.4,
    max_tokens: int = 1024,
    model: str | None = None,
) -> ChatOpenAI:
    return ChatOpenAI(
        model=model or CONFIG.ollama_model,
        api_key="ollama",
        base_url=CONFIG.ollama_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )


@lru_cache(maxsize=2)
def get_sentiment_chat_model(temperature: float = 0.0, max_tokens: int = 700) -> ChatOpenAI:
    return get_chat_model(
        temperature=temperature,
        max_tokens=max_tokens,
        model=CONFIG.sentiment_ollama_model,
    )
