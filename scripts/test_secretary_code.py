#!/usr/bin/env python3
"""
Test script for the new secretary_code_generator API endpoint.
"""

from fastapi.testclient import TestClient
from app.main import app
import json

def test_secretary_code_generator():
    """Test the secretary code generator endpoint."""
    client = TestClient(app)
    
    # Test data matching the API specification
    payload = {
        "clinic_id": 2,
        "doctor_name": "احمد سعد",
        "secretary_name": "مرزوق جلعيطي", 
        "created_date": "10/07/2025 10:00 am"
    }
    
    print("=== Testing Secretary Code Generator API ===")
    print(f"Request payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
    
    # Make POST request to the endpoint
    response = client.post('/api/secretary_code_generator', json=payload)
    
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 200:
        response_data = response.json()
        print(f"Response data: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
        
        # Verify response structure
        assert "secretary_id" in response_data
        assert "result" in response_data
        assert response_data["result"] == "successfuly"
        
        # Verify secretary_id is 6 digits
        secretary_id = response_data["secretary_id"]
        assert 100000 <= secretary_id <= 999999, f"Secretary ID {secretary_id} is not 6 digits"
        
        print(f"✅ Test passed! Generated secretary_id: {secretary_id}")
        
        # Test creating another one to verify uniqueness
        print("\n=== Testing uniqueness with second request ===")
        payload2 = {
            "clinic_id": 3,
            "doctor_name": "فاطمة أحمد",
            "secretary_name": "سارة محمد",
            "created_date": "11/07/2025 02:00 pm"
        }
        
        response2 = client.post('/api/secretary_code_generator', json=payload2)
        print(f"Second response status: {response2.status_code}")
        
        if response2.status_code == 200:
            response2_data = response2.json()
            secretary_id2 = response2_data["secretary_id"]
            print(f"Second secretary_id: {secretary_id2}")
            
            # Verify they are different
            assert secretary_id != secretary_id2, "Secretary IDs should be unique"
            print("✅ Uniqueness test passed!")
        else:
            print(f"❌ Second request failed: {response2.text}")
    else:
        print(f"❌ Test failed with status {response.status_code}")
        print(f"Error details: {response.text}")

if __name__ == "__main__":
    test_secretary_code_generator()