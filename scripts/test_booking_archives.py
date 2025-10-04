import os, json
from fastapi.testclient import TestClient
from app.main import app

# Ensure secret header value
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET','test-secret')
secret = os.environ['DOCTOR_PROFILE_SECRET']
client = TestClient(app)

clinic_id = 456
payload = {
    'clinic_id': clinic_id,
    'table_date': '2025-10-04',
    'capacity_total': 20,
    'capacity_served': 5,
    'capacity_cancelled': 2,
    'patients': [
        {'name': 'Test Patient', 'status': 'booked', 'booking_id': 'X-456-20251004-001'}
    ]
}

r = client.post('/api/save_table', json=payload, headers={'Doctor-Secret': secret})
print('POST /api/save_table ->', r.status_code, r.json())

r2 = client.get(f'/api/booking_archives/{clinic_id}', headers={'Doctor-Secret': secret})
print('GET /api/booking_archives/{clinic_id} ->', r2.status_code)
print(json.dumps(r2.json(), ensure_ascii=False))
