
import sys, os; sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def must(cond, msg):
    if not cond:
        raise SystemExit(f"FAIL: {msg}")

def main():
    # Health
    r = client.get('/health')
    print('HEALTH', r.status_code, r.text)
    must(r.status_code == 200, 'health not 200')

    # Register
    email = f"test-{uuid.uuid4().hex[:8]}@tabeby.app"
    password = 'Passw0rd!'
    r = client.post('/auth/admin/register', json={'name':'Tester','email':email,'password':password})
    print('REGISTER', r.status_code, r.text)
    must(r.status_code in (200,201), 'register failed')

    # Login
    r = client.post('/auth/login', json={'email':email,'password':password})
    print('LOGIN', r.status_code, r.text)
    must(r.status_code == 200, 'login failed')
    data = r.json().get('data')
    must(isinstance(data, dict), 'login response missing data')
    acc = data.get('accessToken')
    ref = data.get('refreshToken')
    must(acc and ref, 'tokens missing')

    # Me
    hdr = {'Authorization': f'Bearer {acc}'}
    r = client.get('/users/me', headers=hdr)
    print('ME', r.status_code, r.text)
    must(r.status_code == 200, 'me failed')

    # Refresh
    r = client.post('/auth/refresh', json={'refreshToken': ref})
    print('REFRESH', r.status_code, r.text)
    must(r.status_code == 200, 'refresh failed')

    print('PASS: self test ok')

if __name__ == '__main__':
    main()
