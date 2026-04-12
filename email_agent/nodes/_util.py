"""Shared helpers for LLM nodes."""
from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from email_agent.llm import get_chat_model

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(raw: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(raw)
        if not match:
            raise
        return json.loads(match.group(0))


def llm_json(system: str, user: str, *, temperature: float = 0.2, max_tokens: int = 1024) -> dict:
    """Ask the chat model and parse a JSON response."""
    model = get_chat_model(temperature=temperature, max_tokens=max_tokens)
    response = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    text = response.content if isinstance(response.content, str) else str(response.content)
    return extract_json(text)
