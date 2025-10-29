"""
Test the new all_clinics_golden_payments endpoint
"""
from fastapi.testclient import TestClient
from app.main import app
import os
import json

client = TestClient(app)

# Set secret for authentication
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print('='*70)
print('Test: Get All Clinics Golden Payments (Admin View)')
print('='*70)

print('\n[GET] /api/all_clinics_golden_payments')
r = client.get('/api/all_clinics_golden_payments', headers=headers)
print(f'Status: {r.status_code}')
print(f'\nResponse:')
print(json.dumps(r.json(), indent=2, ensure_ascii=False))

print('\n' + '='*70)
print('CURL Command:')
print('='*70)
print('''
curl -X GET "http://localhost:8000/api/all_clinics_golden_payments" \\
  -H "Doctor-Secret: your-secret-here"
''')

print('\n' + '='*70)
print('Expected Response Structure:')
print('='*70)
example = {
    "total_clinics": 3,
    "total_payments": 45,
    "total_amount": 67500,
    "total_paid": 45000,
    "total_remain": 22500,
    "clinics": [
        {
            "clinic_id": 4,
            "total_patients": 20,
            "total_amount": 30000,
            "total_paid": 22500,
            "remain_amount": 7500,
            "months": {
                "2025-10": {
                    "patient_count": 10,
                    "amount": 15000,
                    "payment_status": "paid"
                },
                "2025-11": {
                    "patient_count": 10,
                    "amount": 15000,
                    "payment_status": "not_paid"
                }
            }
        },
        {
            "clinic_id": 6,
            "total_patients": 15,
            "total_amount": 22500,
            "total_paid": 15000,
            "remain_amount": 7500,
            "months": {
                "2025-10": {
                    "patient_count": 10,
                    "amount": 15000,
                    "payment_status": "paid"
                },
                "2025-11": {
                    "patient_count": 5,
                    "amount": 7500,
                    "payment_status": "not_paid"
                }
            }
        },
        {
            "clinic_id": 8,
            "total_patients": 10,
            "total_amount": 15000,
            "total_paid": 7500,
            "remain_amount": 7500,
            "months": {
                "2025-10": {
                    "patient_count": 5,
                    "amount": 7500,
                    "payment_status": "paid"
                },
                "2025-11": {
                    "patient_count": 5,
                    "amount": 7500,
                    "payment_status": "not_paid"
                }
            }
        }
    ]
}
print(json.dumps(example, indent=2, ensure_ascii=False))

print('\n' + '='*70)
print('API Details:')
print('='*70)
print('''
هذا الـ API مفيد للأدمن لرؤية نظرة شاملة على:
✓ عدد العيادات المشتركة في Golden Bookings
✓ إجمالي عدد المدفوعات عبر جميع العيادات
✓ المبلغ الإجمالي والمدفوع والمتبقي
✓ تفاصيل كل عيادة (عدد المرضى، المبالغ، الأشهر)
✓ حالة الدفع لكل شهر في كل عيادة
''')
