import os
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print('=' * 70)
print('Testing phone formats')
print('=' * 70)

tests = [
    ('phone=+46765588441', 'plus sign'),
    ('phone=%2B46765588441', 'encoded plus'),
    ('phone=46765588441', 'no plus'),
    ('phone= 46765588441', 'space instead of plus'),
    ('phone=+9647701234567', 'iraq number'),
]

for query, desc in tests:
    print(f'\nTest: {desc}')
    print(f'Query: {query}')
    r = client.get(f'/auth/check-phone?{query}')
    print(f'Status: {r.status_code}')
    data = r.json()
    if r.status_code == 200:
        print(f'OK - Phone: {data["phone_number"]}')
        print(f'Exists: {data["exists"]}')
        if data['exists']:
            print(f'Role: {data["user_role"]}')
    else:
        print(f'ERROR: {data.get("error", {})}')

print('\n' + '=' * 70)
