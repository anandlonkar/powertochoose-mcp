"""Integration test for cost calculator."""

import pytest
from powertochoose_mcp.calculator import CostCalculator, calculate_plan_costs
from powertochoose_mcp.models import RateStructure, CostBreakdown


def test_cost_calculator_simple_rate():
    """Test cost calculator with simple flat rate."""
    rate_structure = RateStructure(
        plan_type="fixed",
        base_charge=9.95,
        tiers=[{"start_kwh": 0, "end_kwh": None, "rate_per_kwh": 0.10}],
        tdu_delivery_rate=0.04,
        renewable_percentage=None,
        has_time_of_use=False,
        early_termination_fee=None,
    )
    
    calculator = CostCalculator(rate_structure)
    cost_1000 = calculator.calculate_cost(1000)
    
    # Verify breakdown
    assert cost_1000.usage_kwh == 1000
    assert cost_1000.base_charge_usd == 9.95
    assert cost_1000.energy_charge_usd == 100.0  # 1000 * 0.10
    assert cost_1000.tdu_delivery_usd == 40.0  # 1000 * 0.04
    
    # Total should be base + energy + TDU + taxes (~7%)
    expected_subtotal = 9.95 + 100.0 + 40.0
    expected_taxes = expected_subtotal * 0.07
    expected_total = expected_subtotal + expected_taxes
    
    assert abs(cost_1000.total_monthly_usd - expected_total) < 0.01


def test_cost_calculator_tiered_rate():
    """Test cost calculator with tiered rates."""
    rate_structure = RateStructure(
        plan_type="fixed",
        base_charge=9.95,
        tiers=[
            {"start_kwh": 0, "end_kwh": 500, "rate_per_kwh": 0.095},
            {"start_kwh": 500, "end_kwh": None, "rate_per_kwh": 0.085},
        ],
        tdu_delivery_rate=0.04,
        renewable_percentage=None,
        has_time_of_use=False,
        early_termination_fee=None,
    )
    
    calculator = CostCalculator(rate_structure)
    cost_1000 = calculator.calculate_cost(1000)
    
    # Energy cost: (500 * 0.095) + (500 * 0.085) = 47.5 + 42.5 = 90.0
    assert cost_1000.energy_charge_usd == 90.0
    
    # Verify tier breakdown
    assert len(cost_1000.breakdown_by_tier) == 2
    assert cost_1000.breakdown_by_tier[0].kwh == 500
    assert cost_1000.breakdown_by_tier[0].rate == 0.095
    assert cost_1000.breakdown_by_tier[1].kwh == 500
    assert cost_1000.breakdown_by_tier[1].rate == 0.085


def test_calculate_plan_costs():
    """Test calculate_plan_costs function for all tiers."""
    rate_structure = RateStructure(
        plan_type="fixed",
        base_charge=9.95,
        tiers=[{"start_kwh": 0, "end_kwh": None, "rate_per_kwh": 0.10}],
        tdu_delivery_rate=0.04,
        renewable_percentage=100,
        has_time_of_use=False,
        early_termination_fee=150.0,
    )
    
    costs = calculate_plan_costs(rate_structure)
    
    # Should have all three tiers
    assert "cost_500_kwh" in costs
    assert "cost_1000_kwh" in costs
    assert "cost_2000_kwh" in costs
    
    # Verify 500 kWh cost
    cost_500 = costs["cost_500_kwh"]
    assert cost_500["usage_kwh"] == 500
    assert cost_500["energy_charge_usd"] == 50.0  # 500 * 0.10
    
    # Verify 2000 kWh cost
    cost_2000 = costs["cost_2000_kwh"]
    assert cost_2000["usage_kwh"] == 2000
    assert cost_2000["energy_charge_usd"] == 200.0  # 2000 * 0.10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
