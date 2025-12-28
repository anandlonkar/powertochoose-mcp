"""
Test script for the FastAPI server locally.
"""

import requests
import json

BASE_URL = "http://localhost:8000"


def test_root():
    """Test root endpoint."""
    print("Testing root endpoint...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()


def test_health():
    """Test health check endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()


def test_plans_browse():
    """Test browsing plans."""
    print("Testing plans browse endpoint...")
    response = requests.get(f"{BASE_URL}/api/plans/75074")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    print()


def test_csv_upload():
    """Test CSV upload (requires sample CSV)."""
    print("Testing CSV upload endpoint...")
    
    # This requires a sample CSV file
    # For now, just test the endpoint without upload
    print("Note: CSV upload test requires sample file")
    print("Use this curl command to test:")
    print('curl -X POST "http://localhost:8000/api/analyze" \\')
    print('  -F "csv_file=@sample.csv" \\')
    print('  -F "zip_code=75074"')
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("PowerToChoose API Server - Local Tests")
    print("=" * 60)
    print()
    
    print("Make sure the server is running:")
    print("  python -m powertochoose_mcp.api_server")
    print()
    
    try:
        test_root()
        test_health()
        test_plans_browse()
        test_csv_upload()
        
        print("✅ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server")
        print("Make sure the API server is running on port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")
