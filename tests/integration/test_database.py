"""Integration test for database operations."""

import pytest
from datetime import datetime
from powertochoose_mcp.db import (
    init_database,
    get_session,
    store_plan,
    get_plans_by_zip,
    get_plan_by_id,
    log_request,
)


@pytest.fixture(scope="module")
def test_db():
    """Initialize test database."""
    # Use in-memory database for testing
    import os
    os.environ["DATABASE_PATH"] = ":memory:"
    
    init_database()
    yield
    
    # Cleanup handled by in-memory database


def test_store_and_retrieve_plan(test_db):
    """Test storing and retrieving a plan."""
    plan_data = {
        "id": "test_plan_001",
        "name": "Test Green Plan",
        "provider": "Test Provider",
        "zip_code": "75035",
        "contract_length_months": 12,
        "renewable_percentage": 100,
        "cancellation_fee": 150.0,
        "rate_structure": {"plan_type": "fixed", "base_charge": 9.95, "tiers": []},
        "cost_500_kwh": {"usage_kwh": 500, "total_monthly_usd": 75.0},
        "cost_1000_kwh": {"usage_kwh": 1000, "total_monthly_usd": 140.0},
        "cost_2000_kwh": {"usage_kwh": 2000, "total_monthly_usd": 270.0},
        "efl_url": "http://example.com/efl.pdf",
        "plan_url": "http://example.com/plan",
        "efl_parsed": True,
    }
    
    classifications = ["green", "100_renewable", "fixed_rate"]
    
    with get_session() as session:
        # Store plan
        plan = store_plan(session, plan_data, classifications)
        assert plan.id == "test_plan_001"
        assert plan.name == "Test Green Plan"
    
    # Retrieve plan
    with get_session() as session:
        retrieved_plan = get_plan_by_id(session, "test_plan_001")
        assert retrieved_plan is not None
        assert retrieved_plan.name == "Test Green Plan"
        assert retrieved_plan.zip_code == "75035"
        assert len(retrieved_plan.classifications) == 3


def test_get_plans_by_zip(test_db):
    """Test retrieving plans by ZIP code."""
    # Store multiple plans
    for i in range(3):
        plan_data = {
            "id": f"test_plan_zip_{i}",
            "name": f"Test Plan {i}",
            "provider": "Test Provider",
            "zip_code": "75024",
            "contract_length_months": 12,
            "renewable_percentage": 50,
            "cancellation_fee": 150.0,
            "rate_structure": {"plan_type": "fixed", "base_charge": 9.95, "tiers": []},
            "cost_500_kwh": {"usage_kwh": 500, "total_monthly_usd": 75.0},
            "cost_1000_kwh": {"usage_kwh": 1000, "total_monthly_usd": 140.0},
            "cost_2000_kwh": {"usage_kwh": 2000, "total_monthly_usd": 270.0},
            "efl_url": "http://example.com/efl.pdf",
            "plan_url": "http://example.com/plan",
            "efl_parsed": True,
        }
        
        classifications = ["green"] if i == 0 else ["fixed_rate"]
        
        with get_session() as session:
            store_plan(session, plan_data, classifications)
    
    # Retrieve all plans for ZIP
    with get_session() as session:
        plans = get_plans_by_zip(session, "75024")
        assert len(plans) == 3
    
    # Filter by classification
    with get_session() as session:
        green_plans = get_plans_by_zip(session, "75024", classifications=["green"])
        assert len(green_plans) == 1
        assert green_plans[0].name == "Test Plan 0"


def test_log_request(test_db):
    """Test logging MCP requests."""
    with get_session() as session:
        log_request(
            session,
            tool_name="search_plans",
            parameters={"zip_code": "75035", "classifications": ["green"]},
            result_count=5,
        )
    
    # Verify log was created
    with get_session() as session:
        from powertochoose_mcp.db.schema import RequestLog
        logs = session.query(RequestLog).all()
        assert len(logs) > 0
        assert logs[-1].tool_name == "search_plans"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
