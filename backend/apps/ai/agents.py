"""Agent factories — each returns a callable that runs one node of the briefing graph."""
from __future__ import annotations

import json
import logging
from typing import Callable

from django.conf import settings
from langchain_core.callbacks import CallbackManager
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from apps.ai.prompts import VERSIONS

log = logging.getLogger("strata.agents")


def _llm(temperature: float | None = None) -> ChatOpenAI:
    cfg = settings.cfg
    return ChatOpenAI(
        model=cfg.OPENAI_MODEL,
        api_key=cfg.OPENAI_API_KEY or "missing-key",  # langchain demands a non-empty string
        temperature=temperature if temperature is not None else cfg.OPENAI_TEMPERATURE,
        max_tokens=cfg.OPENAI_MAX_TOKENS,
    )


def build_structure_narrator(prompt_version: str = "v1") -> Callable[[dict], str]:
    sys = VERSIONS[prompt_version].structure_narrator

    def run(payload: dict) -> str:
        llm = _llm(temperature=0.3)
        resp = llm.invoke([
            SystemMessage(content=sys),
            HumanMessage(content=json.dumps(payload, default=str)),
        ])
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    return run


def build_wyckoff_classifier(prompt_version: str = "v1") -> Callable[[dict], dict]:
    sys = VERSIONS[prompt_version].wyckoff_classifier

    def run(payload: dict) -> dict:
        llm = _llm(temperature=0.1)
        resp = llm.invoke([
            SystemMessage(content=sys + "\nReturn ONLY a JSON object, no surrounding prose."),
            HumanMessage(content=json.dumps(payload, default=str)),
        ])
        return _extract_json(resp.content)
    return run


def build_risk_reviewer(prompt_version: str = "v1") -> Callable[[dict], dict]:
    sys = VERSIONS[prompt_version].risk_reviewer

    def run(payload: dict) -> dict:
        llm = _llm(temperature=0.0)
        resp = llm.invoke([
            SystemMessage(content=sys + "\nReturn ONLY a JSON object, no surrounding prose."),
            HumanMessage(content=json.dumps(payload, default=str)),
        ])
        return _extract_json(resp.content)
    return run


def build_formatter(prompt_version: str = "v1") -> Callable[[dict], str]:
    sys = VERSIONS[prompt_version].formatter

    def run(payload: dict) -> str:
        llm = _llm(temperature=0.2)
        resp = llm.invoke([
            SystemMessage(content=sys),
            HumanMessage(content=json.dumps(payload, default=str)),
        ])
        return resp.content if isinstance(resp.content, str) else str(resp.content)
    return run


def _extract_json(content: str | list) -> dict:
    """Robust JSON extraction — tolerates fenced blocks and leading prose."""
    if isinstance(content, list):
        content = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        log.warning("agent returned non-JSON content", extra={"snippet": text[:200]})
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        log.warning("agent returned malformed JSON", extra={"snippet": text[start : end + 1][:200]})
        return {}
