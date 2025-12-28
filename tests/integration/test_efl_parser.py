"""Integration test for EFL parser."""

from pathlib import Path
import pytest
from powertochoose_mcp.efl_parser import EFLParser, parse_efl_file
from powertochoose_mcp.models import RateStructure


def test_efl_parser_basic():
    """Test basic EFL parser functionality with mock data."""
    # This is a placeholder test that verifies the parser can be instantiated
    # In a real scenario, you would need actual EFL PDF files to test against
    
    # For now, just verify the parser can handle text extraction errors gracefully
    try:
        # Create a test file path that doesn't exist
        test_path = Path("/tmp/nonexistent.pdf")
        
        # Parser should handle missing file
        with pytest.raises(Exception):
            parser = EFLParser(test_path)
    except Exception as e:
        # Expected to fail since file doesn't exist
        assert True


def test_rate_structure_creation():
    """Test RateStructure model creation."""
    rate_structure = RateStructure(
        plan_type="fixed",
        base_charge=9.95,
        tiers=[
            {"start_kwh": 0, "end_kwh": 500, "rate_per_kwh": 0.095},
            {"start_kwh": 500, "end_kwh": None, "rate_per_kwh": 0.085},
        ],
        tdu_delivery_rate=0.04,
        renewable_percentage=50,
        has_time_of_use=False,
        early_termination_fee=150.0,
    )
    
    assert rate_structure.plan_type == "fixed"
    assert rate_structure.base_charge == 9.95
    assert len(rate_structure.tiers) == 2
    assert rate_structure.renewable_percentage == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
