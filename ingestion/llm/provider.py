"""Pluggable LLM provider for text parsing (brief 5.1).

Three backends behind one interface:
  - "regex"     : offline, no model, deterministic keyword extraction (default)
  - "ollama"    : self-hosted Llama3/Mistral -- brief-PREFERRED, no data leaves env
  - "anthropic" : Claude API with strict data-minimisation

CRITICAL (brief 5.1): only isolated text snippets are ever passed here. GPL
internal financial data (costs, margins, Salesforce records) must NEVER reach
this layer. Callers pass a single note/article string and nothing else.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from config import get_settings


@dataclass
class ExtractionResult:
    signals: dict          # structured extraction
    relevance: str         # high | medium | low
    summary: str
    backend: str           # which provider produced this


class LLMProvider:
    """Base interface."""

    name = "base"

    def extract(self, text: str, task: str) -> ExtractionResult:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Regex / keyword backend -- always available, fully offline
# --------------------------------------------------------------------------- #
class RegexProvider(LLMProvider):
    name = "regex"

    INFRA_KEYWORDS = {
        "metro": ["metro", "namma metro", "bmrcl", "rail corridor"],
        "it_park": ["it park", "tech park", "sez", "itpl", "campus"],
        "road": ["highway", "flyover", "road widening", "nhai", "expressway", "orr"],
        "airport": ["airport"],
    }
    RISK_KEYWORDS = ["title dispute", "litigation", "encroachment", "stalled", "delay", "khata", "conversion pending"]
    INTEREST_KEYWORDS = ["competing", "other developer", "bidding", "multiple offers", "interest from"]
    POSITIVE = ["high demand", "fast absorption", "premium", "sold out", "appreciation", "growth"]

    def extract(self, text: str, task: str) -> ExtractionResult:
        low = (text or "").lower()
        signals: dict = {}

        infra_hits = [cat for cat, kws in self.INFRA_KEYWORDS.items() if any(k in low for k in kws)]
        if infra_hits:
            signals["infrastructure_mentions"] = infra_hits
        risks = [k for k in self.RISK_KEYWORDS if k in low]
        if risks:
            signals["risk_flags"] = risks
        interest = [k for k in self.INTEREST_KEYWORDS if k in low]
        if interest:
            signals["competitive_interest"] = interest
        positives = [k for k in self.POSITIVE if k in low]
        if positives:
            signals["positive_signals"] = positives

        if risks:
            relevance = "high"
        elif infra_hits or interest or positives:
            relevance = "medium"
        else:
            relevance = "low"

        summary = "; ".join(
            f"{k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in signals.items()
        ) or "no decision-relevant signals detected"
        return ExtractionResult(signals=signals, relevance=relevance, summary=summary, backend=self.name)


# --------------------------------------------------------------------------- #
# Ollama backend -- self-hosted, brief-preferred
# --------------------------------------------------------------------------- #
_PROMPT = (
    "You extract structured real-estate decision signals from a single text "
    "snippet. Return ONLY compact JSON with keys: signals (object), relevance "
    "(high|medium|low), summary (one sentence). Text:\n\n{text}\n"
)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self._cfg = get_settings().llm

    def extract(self, text: str, task: str) -> ExtractionResult:
        import requests  # local import keeps offline runs dependency-free

        try:
            resp = requests.post(
                f"{self._cfg.ollama_host}/api/generate",
                json={"model": self._cfg.ollama_model, "prompt": _PROMPT.format(text=text[:4000]),
                      "stream": False, "format": "json"},
                timeout=60,
            )
            resp.raise_for_status()
            data = json.loads(resp.json()["response"])
            return ExtractionResult(
                signals=data.get("signals", {}),
                relevance=data.get("relevance", "low"),
                summary=data.get("summary", ""),
                backend=self.name,
            )
        except Exception as exc:  # self-hosted model down -> degrade, never crash pipeline
            fallback = RegexProvider().extract(text, task)
            fallback.summary = f"[ollama unavailable: {exc}; used regex fallback] {fallback.summary}"
            fallback.backend = "ollama->regex"
            return fallback


# --------------------------------------------------------------------------- #
# Anthropic backend -- API with data minimisation
# --------------------------------------------------------------------------- #
class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self._cfg = get_settings().llm

    def extract(self, text: str, task: str) -> ExtractionResult:
        if not self._cfg.anthropic_api_key:
            return RegexProvider().extract(text, task)
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._cfg.anthropic_api_key)
            msg = client.messages.create(
                model=self._cfg.anthropic_model,
                max_tokens=400,
                messages=[{"role": "user", "content": _PROMPT.format(text=text[:4000])}],
            )
            data = json.loads(msg.content[0].text)
            return ExtractionResult(
                signals=data.get("signals", {}),
                relevance=data.get("relevance", "low"),
                summary=data.get("summary", ""),
                backend=self.name,
            )
        except Exception as exc:
            fallback = RegexProvider().extract(text, task)
            fallback.summary = f"[anthropic error: {exc}; used regex fallback] {fallback.summary}"
            fallback.backend = "anthropic->regex"
            return fallback


_PROVIDERS = {"regex": RegexProvider, "ollama": OllamaProvider, "anthropic": AnthropicProvider}


def get_llm_provider() -> LLMProvider:
    cfg = get_settings().llm
    return _PROVIDERS.get(cfg.provider, RegexProvider)()
