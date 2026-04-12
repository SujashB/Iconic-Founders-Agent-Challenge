"""LLM client factory.

All LLM calls in this project go through OpenRouter's OpenAI-compatible
Chat Completions endpoint, using a Claude model. We use `langchain-openai`'s
`ChatOpenAI` with a custom `base_url` rather than `langchain-anthropic`
because OpenRouter speaks the OpenAI API shape, not the Anthropic Messages
shape.

The model is selected via OPENROUTER_MODEL in .env (default:
anthropic/claude-opus-4.6-fast). Switching providers later only requires
changing the env var, not any code in the nodes/agents.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from email_agent.config import CONFIG


@lru_cache(maxsize=4)
def get_chat_model(temperature: float = 0.4, max_tokens: int = 1024) -> ChatOpenAI:
    if not CONFIG.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return ChatOpenAI(
        model=CONFIG.openrouter_model,
        api_key=CONFIG.openrouter_api_key,
        base_url=CONFIG.openrouter_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        # OpenRouter recommends sending these headers so calls are attributed
        # correctly on their dashboard. They are optional and harmless.
        default_headers={
            "HTTP-Referer": "https://github.com/iconicfounders/email-agent",
            "X-Title": "IFG Email Drafting Agent",
        },
    )
