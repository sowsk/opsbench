"""Thin multi-provider model client.

Normalizes Anthropic, OpenAI, and Google Gemini behind a single call_model()
function. v0.1 intentionally avoids a heavyweight abstraction (LangChain,
LiteLLM); the goal is to be readable and reproducible.

Pricing snapshot for cost estimation: June 2026. Update when providers change
pricing. If a model is missing from PRICING, cost is reported as 0.0 with a
note in the run summary.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from .http_client import build_http_client

# (input $/M tokens, output $/M tokens)
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.8, 4.0),
    "gpt-5": (5.0, 25.0),
    "gpt-5-mini": (0.5, 2.5),
    "gemini-2.5-pro": (3.5, 14.0),
    "gemini-2.5-flash": (0.3, 1.2),
}


@dataclass
class ModelResponse:
    model: str
    output_text: str
    input_tokens: int
    output_tokens: int
    elapsed_ms: int
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        rates = PRICING.get(self.model)
        if not rates:
            return 0.0
        return (self.input_tokens / 1_000_000) * rates[0] + (self.output_tokens / 1_000_000) * rates[1]


def family_of(model: str) -> str:
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("gpt-"):
        return "openai"
    if model.startswith("gemini-"):
        return "google"
    raise ValueError(f"Unknown model family for {model!r}. Add a prefix mapping in family_of().")


def call_model(model: str, system: str, user: str, max_tokens: int = 512) -> ModelResponse:
    family = family_of(model)
    if family == "anthropic":
        return _call_anthropic(model, system, user, max_tokens)
    if family == "openai":
        return _call_openai(model, system, user, max_tokens)
    if family == "google":
        return _call_google(model, system, user, max_tokens)
    raise AssertionError("unreachable")


def _call_anthropic(model: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    try:
        from anthropic import Anthropic
    except ImportError as e:
        return ModelResponse(model, "", 0, 0, 0, error=f"anthropic not installed: {e}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ModelResponse(model, "", 0, 0, 0, error="ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=api_key, http_client=build_http_client())
    start = time.time()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        output_text = "\n".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        return ModelResponse(
            model=model,
            output_text=output_text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            elapsed_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        return ModelResponse(model, "", 0, 0, int((time.time() - start) * 1000), error=f"{type(exc).__name__}: {exc}")


def _call_openai(model: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    try:
        from openai import OpenAI
    except ImportError as e:
        return ModelResponse(model, "", 0, 0, 0, error=f"openai not installed: {e}")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ModelResponse(model, "", 0, 0, 0, error="OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key, http_client=build_http_client())
    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0]
        output_text = choice.message.content or ""
        usage = resp.usage
        return ModelResponse(
            model=model,
            output_text=output_text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            elapsed_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        return ModelResponse(model, "", 0, 0, int((time.time() - start) * 1000), error=f"{type(exc).__name__}: {exc}")


def _call_google(model: str, system: str, user: str, max_tokens: int) -> ModelResponse:
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as e:
        return ModelResponse(model, "", 0, 0, 0, error=f"google-genai not installed: {e}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return ModelResponse(model, "", 0, 0, 0, error="GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    start = time.time()
    try:
        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        output_text = resp.text or ""
        usage = getattr(resp, "usage_metadata", None)
        return ModelResponse(
            model=model,
            output_text=output_text,
            input_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) if usage else 0,
            elapsed_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        return ModelResponse(model, "", 0, 0, int((time.time() - start) * 1000), error=f"{type(exc).__name__}: {exc}")
