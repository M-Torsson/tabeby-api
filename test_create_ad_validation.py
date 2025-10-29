"""
Test script for create_clinic_ad endpoint with image validation
"""
from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)

# Set secret for authentication
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print('='*60)
print('Test: POST /api/create_clinic_ad with validation')
print('='*60)

# Test 1: Valid ad with correct dimensions (500x250)
print('\n[Test 1] Valid ad with correct image dimensions')
valid_ad = {
    "request_date": "22/10/2025",
    "clinic_name": "عيادة الأسنان",
    "ad_subtitle": "عيادة متخصصة في كل شيء",
    "ad_description": "عرض خاص",
    "ad_phonenumber": "٠١٠١٢٣٤٥٦٧٨",
    "ad_state": "القاهرة",
    "ad_discount": "٢٠",
    "ad_price": "١٠٠",
    "ad_address": "الحي الاول عمارة يعقوبيان",
    "team_message": "رسالة الفريق",
    "ad_image_url": "https://via.placeholder.com/500x250",  # 500x250 image
    "clinic_id": "7",
    "ad_status": "active"
}

r1 = client.post('/api/create_clinic_ad', json=valid_ad, headers=headers)
print(f'Status: {r1.status_code}')
print(f'Response: {r1.json()}')

# Test 2: Invalid dimensions (wrong size)
print('\n[Test 2] Invalid ad with wrong image dimensions')
invalid_ad = {
    "request_date": "22/10/2025",
    "clinic_name": "عيادة الأسنان",
    "ad_state": "القاهرة",
    "ad_image_url": "https://via.placeholder.com/600x300",  # Wrong dimensions
    "clinic_id": "7",
    "ad_status": "false"
}

r2 = client.post('/api/create_clinic_ad', json=invalid_ad, headers=headers)
print(f'Status: {r2.status_code}')
print(f'Response: {r2.json()}')

# Test 3: Check response format
print('\n[Test 3] Check response format matches requirements')
if r1.status_code == 200:
    response = r1.json()
    required_fields = ["ad_ID", "ad_image", "ad_state", "clinic_id", "ad_status", "expierd_date"]
    print('Required fields check:')
    for field in required_fields:
        exists = field in response
        print(f'  {field}: {"✓" if exists else "✗ MISSING"}')
    
    print(f'\nFull response structure:')
    for key in response:
        print(f'  {key}: {type(response[key]).__name__}')

print('\n' + '='*60)
print('Test completed')
print('='*60)
