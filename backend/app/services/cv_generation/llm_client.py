"""Thin wrapper around the Claude API for a single structured pipeline stage call.

Every call: builds a JSON-schema-constrained request from a Pydantic response model
(output_config.format), validates the response against that model before it's ever
used, and records the attempt in llm_runs regardless of success or failure. Never
writes an unvalidated model response into the domain database -- see spec section 13.
"""

import json
import time
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.llm_run import LlmRun

T = TypeVar("T", bound=BaseModel)

# Cached per-MTok USD pricing (input, output). Approximate -- used only for the
# generation cost cap and cost display, not for billing.
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
}
_DEFAULT_PRICING = (3.00, 15.00)


class LlmCallError(Exception):
    pass


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


def call_structured(
    db: Session,
    settings: Settings,
    *,
    stage: str,
    model: str,
    system_prompt: str,
    user_content: str,
    response_model: type[T],
    prompt_version: str,
    job_posting_id: str | None = None,
    cv_generation_id: str | None = None,
    cover_letter_id: str | None = None,
    max_tokens: int = 4096,
    effort: str | None = "medium",
) -> tuple[T, float]:
    """Runs one stage of the pipeline as a single Claude API call.

    Returns (parsed_output, cost_usd). Raises LlmCallError on transport failure,
    non-JSON response, or schema validation failure -- the caller decides whether to
    retry (spec caps LaTeX repair at 2 attempts; the same discipline applies here).
    """
    default_headers = (
        {"anthropic-workspace-id": settings.anthropic_workspace_id}
        if settings.anthropic_workspace_id
        else None
    )
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, default_headers=default_headers)
    schema = response_model.model_json_schema()

    started = time.monotonic()
    status = "error"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost = 0.0
    error_message: str | None = None
    parsed: T | None = None
    call_error: Exception | None = None

    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if effort is not None:
        output_config["effort"] = effort

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            output_config=output_config,
            messages=[{"role": "user", "content": user_content}],
        )
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = estimate_cost_usd(model, input_tokens, output_tokens)

        if response.stop_reason == "refusal":
            raise LlmCallError(f"{stage}: model refused the request")
        if response.stop_reason == "max_tokens":
            raise LlmCallError(
                f"{stage}: response truncated at max_tokens={max_tokens} before completing valid JSON "
                "-- increase max_tokens for this stage or reduce input size"
            )

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LlmCallError(f"{stage}: no text block in response")

        data = json.loads(text)
        parsed = response_model.model_validate(data)
        status = "success"
    except (anthropic.APIError, json.JSONDecodeError, ValidationError, LlmCallError) as exc:
        error_message = str(exc)[:2000]
        call_error = exc
    finally:
        latency_ms = int((time.monotonic() - started) * 1000)
        db.add(
            LlmRun(
                job_posting_id=job_posting_id,
                cv_generation_id=cv_generation_id,
                cover_letter_id=cover_letter_id,
                stage=stage,
                provider="anthropic",
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                status=status,
                error=error_message,
            )
        )
        db.commit()

    if call_error is not None:
        raise LlmCallError(f"{stage} call failed: {error_message}") from call_error

    assert parsed is not None
    return parsed, cost
