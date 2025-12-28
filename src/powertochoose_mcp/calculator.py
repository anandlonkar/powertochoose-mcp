"""Cost calculator for electricity plans.

Calculates costs at standard usage tiers (500, 1000, 2000 kWh/month) based on
rate structures parsed from EFLs.
"""

from typing import Dict, Any, List

from .models import RateStructure, CostBreakdown, RateTier
from .config import USAGE_TIERS


class CostCalculator:
    """Calculator for plan costs at different usage levels."""

    def __init__(self, rate_structure: RateStructure):
        """Initialize calculator with rate structure.

        Args:
            rate_structure: Parsed rate structure from EFL
        """
        self.rate_structure = rate_structure

    def calculate_all_tiers(self) -> Dict[str, CostBreakdown]:
        """Calculate costs for all standard usage tiers.

        Returns:
            Dictionary mapping usage tier to cost breakdown
        """
        return {
            f"cost_{usage}_kwh": self.calculate_cost(usage)
            for usage in USAGE_TIERS
        }

    def calculate_cost(self, usage_kwh: int) -> CostBreakdown:
        """Calculate cost for a specific usage level.

        Args:
            usage_kwh: Usage in kWh per month

        Returns:
            CostBreakdown object with detailed cost information
        """
        # Calculate energy charge using tiered rates
        energy_breakdown = self._calculate_energy_cost(usage_kwh)
        energy_cost = sum(tier["cost"] for tier in energy_breakdown)

        # Calculate TDU delivery charge
        tdu_cost = self._calculate_tdu_cost(usage_kwh)

        # Estimate taxes and fees (typically 5-10% of subtotal)
        subtotal = self.rate_structure.base_charge + energy_cost + tdu_cost
        taxes_fees = subtotal * 0.07  # 7% estimate

        # Total monthly cost
        total = subtotal + taxes_fees

        # Convert breakdown to RateTier objects
        tier_objects = [
            RateTier(
                tier=tier["tier"],
                kwh=tier["kwh"],
                rate=tier["rate"],
                cost=tier["cost"],
            )
            for tier in energy_breakdown
        ]

        # Calculate average energy rate
        avg_rate = energy_cost / usage_kwh if usage_kwh > 0 else 0

        return CostBreakdown(
            usage_kwh=usage_kwh,
            base_charge_usd=round(self.rate_structure.base_charge, 2),
            energy_charge_usd=round(energy_cost, 2),
            energy_rate_per_kwh=round(avg_rate, 4),
            tdu_delivery_usd=round(tdu_cost, 2),
            taxes_fees_usd=round(taxes_fees, 2),
            total_monthly_usd=round(total, 2),
            breakdown_by_tier=tier_objects,
        )

    def _calculate_energy_cost(self, usage_kwh: int) -> List[Dict[str, Any]]:
        """Calculate energy cost using tiered rates.

        Args:
            usage_kwh: Usage in kWh

        Returns:
            List of tier breakdowns
        """
        tiers = self.rate_structure.tiers
        if not tiers:
            # If no tiers, use a default rate
            return [{
                "tier": f"0-{usage_kwh}",
                "kwh": usage_kwh,
                "rate": 0.10,  # Default rate
                "cost": usage_kwh * 0.10,
            }]

        breakdown = []
        remaining_kwh = usage_kwh

        for i, tier_info in enumerate(tiers):
            if remaining_kwh <= 0:
                break

            start_kwh = tier_info["start_kwh"]
            end_kwh = tier_info.get("end_kwh")
            rate = tier_info["rate_per_kwh"]

            # Determine how much usage falls in this tier
            if end_kwh is None:
                # Last tier (no upper bound)
                tier_usage = remaining_kwh
                tier_label = f"{start_kwh}+"
            else:
                # Tier with upper bound
                tier_capacity = end_kwh - start_kwh
                tier_usage = min(remaining_kwh, tier_capacity)
                tier_label = f"{start_kwh}-{end_kwh}"

            tier_cost = tier_usage * rate

            breakdown.append({
                "tier": tier_label,
                "kwh": tier_usage,
                "rate": rate,
                "cost": tier_cost,
            })

            remaining_kwh -= tier_usage

        return breakdown

    def _calculate_tdu_cost(self, usage_kwh: int) -> float:
        """Calculate TDU delivery cost.

        Args:
            usage_kwh: Usage in kWh

        Returns:
            TDU cost in dollars
        """
        if self.rate_structure.tdu_delivery_rate:
            return usage_kwh * self.rate_structure.tdu_delivery_rate

        # If TDU rate not specified, use industry average (~$0.04/kWh)
        return usage_kwh * 0.04


def calculate_plan_costs(rate_structure: RateStructure) -> Dict[str, Dict[str, Any]]:
    """Calculate costs for all standard tiers for a plan.

    Args:
        rate_structure: Parsed rate structure

    Returns:
        Dictionary with cost breakdowns for each tier
    """
    calculator = CostCalculator(rate_structure)
    result = calculator.calculate_all_tiers()

    # Convert CostBreakdown objects to dictionaries
    return {
        key: breakdown.model_dump()
        for key, breakdown in result.items()
    }
