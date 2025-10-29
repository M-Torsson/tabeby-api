"""
Manual test for create_clinic_ad endpoint
This test uses actual image URLs to verify dimension and size validation
"""
import requests
import json

# API Configuration
BASE_URL = "https://tabeby-api.onrender.com"
SECRET = "your-secret-here"  # Replace with actual secret

headers = {
    "Doctor-Secret": SECRET,
    "Content-Type": "application/json"
}

print('='*70)
print('Manual Test: POST /api/create_clinic_ad')
print('='*70)

# Test 1: Valid ad with correct dimensions (500x250)
print('\n[Test 1] Create ad with valid image (500x250)')
valid_ad = {
    "request_date": "29/10/2025",
    "clinic_name": "عيادة الأسنان",
    "ad_subtitle": "عيادة متخصصة في كل شيء",
    "ad_description": "عرض خاص على تنظيف الأسنان",
    "ad_phonenumber": "٠١٠١٢٣٤٥٦٧٨",
    "ad_state": "القاهرة",
    "ad_discount": "٢٠",
    "ad_price": "١٠٠",
    "ad_address": "الحي الاول عمارة يعقوبيان",
    "team_message": "نقدم أفضل خدمات الأسنان",
    "ad_image_url": "https://via.placeholder.com/500x250.png",  # Correct dimensions
    "clinic_id": "7",
    "ad_status": "false"
}

try:
    r1 = requests.post(f'{BASE_URL}/api/create_clinic_ad', 
                      json=valid_ad, 
                      headers=headers,
                      timeout=30)
    print(f'Status: {r1.status_code}')
    print(f'Response:')
    print(json.dumps(r1.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f'Error: {e}')

# Test 2: Invalid dimensions (600x300)
print('\n[Test 2] Create ad with invalid dimensions (600x300)')
invalid_ad = {
    "request_date": "29/10/2025",
    "clinic_name": "عيادة الأسنان 2",
    "ad_state": "بغداد",
    "ad_image_url": "https://via.placeholder.com/600x300.png",  # Wrong dimensions
    "clinic_id": "8",
    "ad_status": "false"
}

try:
    r2 = requests.post(f'{BASE_URL}/api/create_clinic_ad', 
                      json=invalid_ad, 
                      headers=headers,
                      timeout=30)
    print(f'Status: {r2.status_code}')
    print(f'Response:')
    print(json.dumps(r2.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f'Error: {e}')

# Test 3: Missing required field
print('\n[Test 3] Missing required field (ad_state)')
missing_field = {
    "clinic_name": "عيادة الأسنان 3",
    "ad_image_url": "https://via.placeholder.com/500x250.png",
    "clinic_id": "9",
    "ad_status": "false"
}

try:
    r3 = requests.post(f'{BASE_URL}/api/create_clinic_ad', 
                      json=missing_field, 
                      headers=headers,
                      timeout=30)
    print(f'Status: {r3.status_code}')
    print(f'Response:')
    print(json.dumps(r3.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(f'Error: {e}')

print('\n' + '='*70)
print('Test Instructions:')
print('1. Replace SECRET with your actual DOCTOR_PROFILE_SECRET')
print('2. Run: python test_manual_ad_creation.py')
print('3. Verify response format matches:')
print('   {')
print('     "ad_ID": "...",')
print('     "ad_image": "...",')
print('     "ad_state": "...",')
print('     "clinic_id": ...,')
print('     "ad_status": false,')
print('     "expierd_date": "..."')
print('   }')
print('='*70)
