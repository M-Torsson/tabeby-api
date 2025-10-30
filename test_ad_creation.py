"""
Test ad creation endpoint
"""
from fastapi.testclient import TestClient
from app.main import app
import os

client = TestClient(app)

# Doctor-Secret من البيئة
secret = os.getenv('DOCTOR_PROFILE_SECRET', 'test-secret')
headers = {'Doctor-Secret': secret}

# بيانات الإعلان
payload = {
    "request_date": "30/10/2025",
    "clinic_name": "عيادة الاختبار",
    "ad_subtitle": "عيادة متخصصة",
    "ad_description": "عرض خاص",
    "ad_phonenumber": "01012345678",
    "ad_state": "القاهرة",
    "ad_discount": "20",
    "ad_price": "100",
    "ad_address": "شارع التحرير",
    "team_message": "رسالة الفريق",
    "ad_image_url": "https://example.com/image.jpg",
    "clinic_id": "7",
    "ad_status": "active"
}

print('[POST] /api/create_clinic_ad')
print('Payload:', payload)
print()

r = client.post('/api/create_clinic_ad', json=payload, headers=headers)
print('Status:', r.status_code)
print('Response:', r.json() if r.status_code != 500 else r.text)
print()

if r.status_code == 200:
    ad_id = r.json().get('ad_ID')
    print(f'✅ Ad created successfully with ID: {ad_id}')
else:
    print('❌ Failed to create ad')
