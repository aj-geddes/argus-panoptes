"""Cost calculator service — config-driven token pricing."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Pricing is in dollars per million tokens
_TOKENS_PER_UNIT = 1_000_000


class CostCalculator:
    """Calculates costs for LLM API calls based on config-driven pricing tables."""

    def __init__(self, cost_model_config: dict[str, Any]) -> None:
        self._providers: dict[str, dict[str, dict[str, float]]] = cost_model_config.get("providers", {})

    def calculate(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate the cost in USD for a given model usage.

        Pricing is per million tokens, sourced from config.

        Returns 0.0 if provider/model is unknown.
        """
        pricing = self.get_pricing(provider, model)
        if pricing is None:
            return 0.0

        input_cost = (input_tokens / _TOKENS_PER_UNIT) * pricing["input"]
        output_cost = (output_tokens / _TOKENS_PER_UNIT) * pricing["output"]
        return input_cost + output_cost

    def get_pricing(self, provider: str, model: str) -> dict[str, float] | None:
        """Get the pricing rates for a provider/model pair.

        Returns a dict with 'input' and 'output' keys ($/M tokens), or None.
        """
        provider_models = self._providers.get(provider)
        if provider_models is None:
            return None
        model_pricing = provider_models.get(model)
        if model_pricing is None:
            return None
        return model_pricing

    def update_config(self, cost_model_config: dict[str, Any]) -> None:
        """Update the pricing config (for hot-reload support)."""
        self._providers = cost_model_config.get("providers", {})
        logger.info("Cost model config updated (%d providers)", len(self._providers))
