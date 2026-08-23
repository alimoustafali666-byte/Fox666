"""Configurable provider pricing for the cost projection report --
deliberately NOT hardcoded into metrics/report logic, since pricing
changes over time (spec: "Keep provider pricing configurable because
pricing changes... Do not build billing.").

Defaults below are Anthropic's own published per-1M-token rates for
claude-sonnet-5 as cached by this project's claude-api skill
(2026-06-24) -- NOT independently verified against a live pricing page
in this environment, same disclosure category as the model identifier
itself. Override via EVAL_CLAUDE_INPUT_PRICE_PER_1M /
EVAL_CLAUDE_OUTPUT_PRICE_PER_1M. Voyage's per-token price has no cached,
disclosed reference in this codebase, so it defaults to None (omitted
from the cost projection rather than guessed) unless
EVAL_VOYAGE_PRICE_PER_1M_TOKENS is explicitly set.
"""

import os
from dataclasses import dataclass


@dataclass
class ProviderPricing:
    claude_input_per_1m: float
    claude_output_per_1m: float
    voyage_per_1m_tokens: float | None
    source_note: str


def load_pricing() -> ProviderPricing:
    voyage_env = os.environ.get("EVAL_VOYAGE_PRICE_PER_1M_TOKENS")
    return ProviderPricing(
        claude_input_per_1m=float(os.environ.get("EVAL_CLAUDE_INPUT_PRICE_PER_1M", "3.00")),
        claude_output_per_1m=float(os.environ.get("EVAL_CLAUDE_OUTPUT_PRICE_PER_1M", "15.00")),
        voyage_per_1m_tokens=float(voyage_env) if voyage_env else None,
        source_note=(
            "claude-sonnet-5 defaults from the claude-api skill's cached model table "
            "(2026-06-24), not independently verified live; override via "
            "EVAL_CLAUDE_INPUT_PRICE_PER_1M/EVAL_CLAUDE_OUTPUT_PRICE_PER_1M. Voyage pricing "
            "has no cached reference and is omitted unless EVAL_VOYAGE_PRICE_PER_1M_TOKENS is set."
        ),
    )


def cost_per_question(
    *, avg_input_tokens: float, avg_output_tokens: float, pricing: ProviderPricing
) -> float:
    return (
        avg_input_tokens / 1_000_000 * pricing.claude_input_per_1m
        + avg_output_tokens / 1_000_000 * pricing.claude_output_per_1m
    )


def daily_cost_projection(
    *, questions_per_day: int, avg_input_tokens: float, avg_output_tokens: float,
    pricing: ProviderPricing,
) -> float:
    per_question = cost_per_question(
        avg_input_tokens=avg_input_tokens, avg_output_tokens=avg_output_tokens, pricing=pricing
    )
    return round(per_question * questions_per_day, 4)

