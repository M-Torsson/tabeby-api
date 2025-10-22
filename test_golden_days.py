import os
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)

# Test with non-existent clinic
r = c.get('/api/booking_golden_days?clinic_id=999', headers={'Doctor-Secret': 'test-secret'})
print('STATUS:', r.status_code)
print('BODY:', r.json())

# Test with clinic 85
r2 = c.get('/api/booking_golden_days?clinic_id=85', headers={'Doctor-Secret': 'test-secret'})
print('\nSTATUS 85:', r2.status_code)
print('BODY 85:', r2.json())
