"""Thin multi-provider model client.

Normalizes Anthropic, OpenAI, and Google Gemini behind a single call_model()
function. OpsBench intentionally avoids a heavyweight abstraction (LangChain,
LiteLLM); the goal is to be readable and reproducible.

Pricing snapshot for cost estimation: August 7, 2026. Update when providers change
pricing. If a model is missing from PRICING, cost is reported as 0.0 with a
note in the run summary.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from .http_client import build_http_client

# Standard short-context pricing in USD per 1M tokens, snapshot 2026-08-07.
# OpsBench prompts are far below provider long-context pricing thresholds.
# Anthropic Sonnet 5 uses its introductory price through 2026-08-31.
# (input $/M tokens, output $/M tokens)
PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "gpt-5.6-sol": (5.0, 30.0),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-luna": (0.2, 1.2),
    "gpt-5": (1.25, 10.0),
    "gpt-5-mini": (0.25, 2.0),
    "gemini-3.6-flash": (1.5, 7.5),
    "gemini-3.5-flash-lite": (0.3, 2.5),
    "gemini-2.5-pro": (1.25, 10.0),
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
        if model.startswith("gemini-3.6-"):
            thinking_config = genai_types.ThinkingConfig(thinking_level="medium")
            output_budget = max_tokens
        elif model.startswith("gemini-3.5-flash-lite"):
            thinking_config = genai_types.ThinkingConfig(thinking_level="minimal")
            output_budget = max_tokens
        else:
            # Gemini 2.5 Pro cannot disable thinking entirely. Reserve the
            # 128-token minimum so thinking does not consume the visible output.
            thinking_config = genai_types.ThinkingConfig(thinking_budget=128)
            output_budget = max_tokens + 128

        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=output_budget,
                thinking_config=thinking_config,
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
