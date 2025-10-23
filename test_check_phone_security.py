import os
# Set BEFORE importing anything
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret-123'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print('=' * 70)
print('Testing /auth/check-phone with Doctor-Secret header')
print('=' * 70)

# Test 1: بدون header
print('\n[Test 1] Without Doctor-Secret header')
r1 = client.get('/auth/check-phone?phone=+46765588441')
print(f'Status: {r1.status_code}')
print(f'Response: {r1.json()}')

# Test 2: مع header خاطئ
print('\n[Test 2] With wrong Doctor-Secret')
r2 = client.get(
    '/auth/check-phone?phone=+46765588441',
    headers={'Doctor-Secret': 'wrong-secret'}
)
print(f'Status: {r2.status_code}')
print(f'Response: {r2.json()}')

# Test 3: مع header صحيح
print('\n[Test 3] With correct Doctor-Secret')
r3 = client.get(
    '/auth/check-phone?phone=+46765588441',
    headers={'Doctor-Secret': 'test-secret-123'}
)
print(f'Status: {r3.status_code}')
print(f'Response: {r3.json()}')

# Test 4: رقم غير موجود مع header صحيح
print('\n[Test 4] Non-existent phone with correct header')
r4 = client.get(
    '/auth/check-phone?phone=+9647709999999',
    headers={'Doctor-Secret': 'test-secret-123'}
)
print(f'Status: {r4.status_code}')
print(f'Response: {r4.json()}')

print('\n' + '=' * 70)
print('Summary:')
print('  - Without header: Should return 403')
print('  - Wrong header: Should return 403')
print('  - Correct header: Should return 200')
print('=' * 70)
