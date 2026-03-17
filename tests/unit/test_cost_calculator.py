"""Tests for cost calculator service — config-driven pricing."""

from __future__ import annotations

import pytest


@pytest.fixture()
def pricing_config() -> dict:
    """Return a minimal pricing config for testing."""
    return {
        "cost_model": {
            "providers": {
                "openai": {
                    "gpt-4o": {"input": 2.50, "output": 10.00},
                    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
                },
                "anthropic": {
                    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
                    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
                },
            }
        }
    }


class TestCostCalculator:
    """Test suite for the CostCalculator."""

    def test_calculate_cost_known_model(self, pricing_config: dict) -> None:
        """Should calculate cost correctly for a known model."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        # 1000 input tokens at $2.50/M = $0.0025
        # 500 output tokens at $10.00/M = $0.005
        cost = calc.calculate(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost == pytest.approx(0.0075, abs=1e-6)

    def test_calculate_cost_zero_tokens(self, pricing_config: dict) -> None:
        """Should return 0.0 for zero tokens."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        cost = calc.calculate(
            provider="openai",
            model="gpt-4o",
            input_tokens=0,
            output_tokens=0,
        )
        assert cost == 0.0

    def test_calculate_cost_unknown_model(self, pricing_config: dict) -> None:
        """Should return 0.0 for an unknown model."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        cost = calc.calculate(
            provider="openai",
            model="unknown-model-xyz",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost == 0.0

    def test_calculate_cost_unknown_provider(self, pricing_config: dict) -> None:
        """Should return 0.0 for an unknown provider."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        cost = calc.calculate(
            provider="unknown-provider",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        assert cost == 0.0

    def test_calculate_cost_anthropic_model(self, pricing_config: dict) -> None:
        """Should calculate cost for Anthropic models."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        # 2000 input tokens at $3.00/M = $0.006
        # 1000 output tokens at $15.00/M = $0.015
        cost = calc.calculate(
            provider="anthropic",
            model="claude-sonnet-4",
            input_tokens=2000,
            output_tokens=1000,
        )
        assert cost == pytest.approx(0.021, abs=1e-6)

    def test_calculate_cost_large_token_count(self, pricing_config: dict) -> None:
        """Should calculate cost correctly for large token counts."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        # 1M input tokens at $2.50/M = $2.50
        # 1M output tokens at $10.00/M = $10.00
        cost = calc.calculate(
            provider="openai",
            model="gpt-4o",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(12.50, abs=1e-4)

    def test_get_pricing_returns_rates(self, pricing_config: dict) -> None:
        """Should return the pricing rates for a known model."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        pricing = calc.get_pricing("openai", "gpt-4o")
        assert pricing is not None
        assert pricing["input"] == 2.50
        assert pricing["output"] == 10.00

    def test_get_pricing_unknown_returns_none(self, pricing_config: dict) -> None:
        """Should return None for an unknown model."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        pricing = calc.get_pricing("openai", "unknown-model")
        assert pricing is None

    def test_update_config(self, pricing_config: dict) -> None:
        """Should update pricing config dynamically."""
        from argus.services.cost_calculator import CostCalculator

        calc = CostCalculator(pricing_config["cost_model"])
        new_config = {
            "providers": {
                "openai": {
                    "gpt-4o": {"input": 5.00, "output": 20.00},
                },
            }
        }
        calc.update_config(new_config)
        cost = calc.calculate(
            provider="openai",
            model="gpt-4o",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(25.0, abs=1e-4)
