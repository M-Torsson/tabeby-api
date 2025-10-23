import os
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

print('=' * 70)
print('Testing NEW Ad Endpoints')
print('=' * 70)

# Test 1: Create Clinic Ad
print('\n[Test 1] POST /api/create_clinic_ad')
ad_payload = {
    "created_date": "22/10/2025",
    "clinic_name": "عيادة الامال الحالمة",
    "ad_subtitle": "عيادة متخصصة في كل شيء",
    "ad_description": "ما تفسير رؤية الرجل الذي كان يقول في ذلك له وما عليه",
    "ad_phonenumber": "07885441223",
    "ad_state": "كركوك",
    "ad_discount": "30%",
    "ad_price": "20000",
    "team_message": "يا ذا ابن عم الوطن",
    "ad_image_url": "https://firebasestorage.googleapis.com/v0/test.jpg",
    "clinic_id": 6,
    "ad_status": False
}

r1 = client.post('/api/create_clinic_ad', json=ad_payload, headers=headers)
print(f'Status: {r1.status_code}')
if r1.status_code == 200:
    result = r1.json()
    print(f'✅ Ad created!')
    print(f'   ad_ID: {result.get("ad_ID")}')
    print(f'   database_id: {result.get("database_id")}')
    ad_id_created = result.get("ad_ID")
else:
    print(f'❌ Error: {r1.json()}')
    ad_id_created = None

# Test 2: Get Ad by ad_ID
if ad_id_created:
    print(f'\n[Test 2] GET /api/get_ad_image?ad_ID={ad_id_created}')
    r2 = client.get(f'/api/get_ad_image?ad_ID={ad_id_created}', headers=headers)
    print(f'Status: {r2.status_code}')
    if r2.status_code == 200:
        data = r2.json()
        print('✅ Ad retrieved:')
        print(f'   ad_ID: {data.get("ad_ID")}')
        print(f'   ad_image: {data.get("ad_image")}')
        print(f'   ad_state: {data.get("ad_state")}')
        print(f'   clinic_id: {data.get("clinic_id")}')
        print(f'   ad_status: {data.get("ad_status")}')
        print(f'   expired_date: {data.get("expired_date")}')
    else:
        print(f'❌ Error: {r2.json()}')

# Test 3: Get Ads by clinic_id
print('\n[Test 3] GET /api/get_ad_image?clinic_id=6')
r3 = client.get('/api/get_ad_image?clinic_id=6', headers=headers)
print(f'Status: {r3.status_code}')
if r3.status_code == 200:
    result = r3.json()
    print(f'✅ Found {result.get("count")} ads for clinic 6')
    if result['count'] > 0:
        print(f'   First ad: {result["items"][0].get("ad_ID")}')
else:
    print(f'❌ Error: {r3.json()}')

# Test 4: Get All Active Ads
print('\n[Test 4] GET /api/get_all_ads')
r4 = client.get('/api/get_all_ads', headers=headers)
print(f'Status: {r4.status_code}')
if r4.status_code == 200:
    result = r4.json()
    print(f'✅ Total active ads: {result.get("count")}')
else:
    print(f'❌ Error: {r4.json()}')

print('\n' + '=' * 70)
print('Summary:')
print('  - create_clinic_ad: Creates ad with auto-generated ad_ID')
print('  - get_ad_image: Returns ad in required format')
print('  - get_all_ads: Returns all active ads')
print('=' * 70)
