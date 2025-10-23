import os
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print('=' * 70)
print('Testing /api/clinics with state field')
print('=' * 70)

# Test with correct header
response = client.get(
    '/api/clinics',
    headers={'Doctor-Secret': 'test-secret'}
)

print(f'\nStatus: {response.status_code}')

if response.status_code == 200:
    clinics = response.json()
    print(f'Total clinics: {len(clinics)}')
    
    # Show first 3 clinics
    print('\nFirst 3 clinics:')
    for i, clinic in enumerate(clinics[:3], 1):
        print(f'\n[{i}] Clinic ID: {clinic.get("clinic_id")}')
        print(f'    Doctor: {clinic.get("doctor_name")}')
        print(f'    State: {clinic.get("state", "N/A")}')
        print(f'    Status: {clinic.get("status")}')
        print(f'    Specializations: {len(clinic.get("specializations", []))}')
        if clinic.get("profile_image_URL"):
            print(f'    Has Image: Yes')
else:
    print(f'Error: {response.json()}')

print('\n' + '=' * 70)
