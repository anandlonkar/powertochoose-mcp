"""Integration test for MCP server tools."""

import pytest
import json
from powertochoose_mcp.server import search_plans_tool, calculate_plan_cost_tool
from powertochoose_mcp.db import init_database, get_session, store_plan


@pytest.fixture(scope="module")
def test_db_with_data():
    """Initialize test database with sample data."""
    import os
    os.environ["DATABASE_PATH"] = ":memory:"
    
    init_database()
    
    # Create sample plans
    plan_data = {
        "id": "test_mcp_001",
        "name": "MCP Test Plan",
        "provider": "Test REP",
        "zip_code": "75035",
        "contract_length_months": 12,
        "renewable_percentage": 100,
        "cancellation_fee": 150.0,
        "rate_structure": {
            "plan_type": "fixed",
            "base_charge": 9.95,
            "tiers": [{"start_kwh": 0, "end_kwh": None, "rate_per_kwh": 0.10}],
        },
        "cost_500_kwh": {
            "usage_kwh": 500,
            "base_charge_usd": 9.95,
            "energy_charge_usd": 50.0,
            "energy_rate_per_kwh": 0.10,
            "tdu_delivery_usd": 20.0,
            "taxes_fees_usd": 5.60,
            "total_monthly_usd": 85.55,
            "breakdown_by_tier": [],
        },
        "cost_1000_kwh": {
            "usage_kwh": 1000,
            "base_charge_usd": 9.95,
            "energy_charge_usd": 100.0,
            "energy_rate_per_kwh": 0.10,
            "tdu_delivery_usd": 40.0,
            "taxes_fees_usd": 10.50,
            "total_monthly_usd": 160.45,
            "breakdown_by_tier": [],
        },
        "cost_2000_kwh": {
            "usage_kwh": 2000,
            "base_charge_usd": 9.95,
            "energy_charge_usd": 200.0,
            "energy_rate_per_kwh": 0.10,
            "tdu_delivery_usd": 80.0,
            "taxes_fees_usd": 20.30,
            "total_monthly_usd": 310.25,
            "breakdown_by_tier": [],
        },
        "efl_url": "http://example.com/efl.pdf",
        "plan_url": "http://example.com/plan",
        "efl_parsed": True,
    }
    
    classifications = ["green", "100_renewable", "fixed_rate"]
    
    with get_session() as session:
        store_plan(session, plan_data, classifications)
    
    yield


@pytest.mark.asyncio
async def test_search_plans_tool_supported_zip(test_db_with_data):
    """Test search_plans tool with supported ZIP code."""
    arguments = {"zip_code": "75035"}
    
    result = await search_plans_tool(arguments)
    
    assert len(result) == 1
    assert result[0].type == "text"
    
    # Parse JSON response
    data = json.loads(result[0].text)
    
    assert data["zip_code"] == "75035"
    assert data["total_results"] >= 1  # At least one plan
    assert len(data["plans"]) >= 1
    # Check that our test plan is in the results
    plan_names = [p["name"] for p in data["plans"]]
    assert "MCP Test Plan" in plan_names


@pytest.mark.asyncio
async def test_search_plans_tool_unsupported_zip(test_db_with_data):
    """Test search_plans tool with unsupported ZIP code."""
    arguments = {"zip_code": "12345"}
    
    result = await search_plans_tool(arguments)
    
    assert len(result) == 1
    data = json.loads(result[0].text)
    
    assert "message" in data
    assert "coming to your ZIP code soon" in data["message"]


@pytest.mark.asyncio
async def test_search_plans_tool_with_classifications(test_db_with_data):
    """Test search_plans tool with classification filter."""
    arguments = {"zip_code": "75035", "classifications": ["green"]}
    
    result = await search_plans_tool(arguments)
    
    data = json.loads(result[0].text)
    
    assert data["total_results"] >= 1
    # All returned plans should have "green" classification
    for plan in data["plans"]:
        assert "green" in plan["classifications"]


@pytest.mark.asyncio
async def test_calculate_plan_cost_tool(test_db_with_data):
    """Test calculate_plan_cost tool."""
    arguments = {"plan_id": "test_mcp_001"}
    
    result = await calculate_plan_cost_tool(arguments)
    
    assert len(result) == 1
    data = json.loads(result[0].text)
    
    assert data["plan_id"] == "test_mcp_001"
    assert data["plan_name"] == "MCP Test Plan"
    
    # Verify all cost tiers present
    assert "cost_500_kwh" in data
    assert "cost_1000_kwh" in data
    assert "cost_2000_kwh" in data
    
    # Verify 1000 kWh breakdown
    cost_1000 = data["cost_1000_kwh"]
    assert cost_1000["usage_kwh"] == 1000
    assert cost_1000["total_monthly_usd"] == 160.45


@pytest.mark.asyncio
async def test_calculate_plan_cost_tool_not_found(test_db_with_data):
    """Test calculate_plan_cost tool with non-existent plan."""
    arguments = {"plan_id": "nonexistent"}
    
    result = await calculate_plan_cost_tool(arguments)
    
    data = json.loads(result[0].text)
    
    assert "error" in data
    assert "not found" in data["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
