import uuid
import sys
import requests

BASE = 'http://127.0.0.1:8000'

def must(cond, msg):
    if not cond:
        print('FAIL:', msg)
        sys.exit(1)

def main():
    try:
        r = requests.get(BASE + '/health', timeout=5)
        print('HEALTH', r.status_code, r.text)
        must(r.status_code == 200, 'health not 200')
    except Exception as e:
        print('HEALTH error', e)
        sys.exit(1)

    email = f'test-{uuid.uuid4().hex[:8]}@tabeby.app'
    password = 'Passw0rd!'
    r = requests.post(BASE + '/auth/admin/register', json={'name':'Tester','email':email,'password':password})
    print('REGISTER', r.status_code, r.text)
    must(r.status_code in (200,201), 'register failed')

    r = requests.post(BASE + '/auth/login', json={'email':email,'password':password})
    print('LOGIN', r.status_code, r.text)
    must(r.status_code == 200, 'login failed')
    data = r.json().get('data')
    must(isinstance(data, dict), 'login response missing data')
    acc = data.get('accessToken')
    ref = data.get('refreshToken')
    must(acc and ref, 'tokens missing')

    hdr = {'Authorization': f'Bearer {acc}'}
    r = requests.get(BASE + '/users/me', headers=hdr)
    print('ME', r.status_code, r.text)
    must(r.status_code == 200, 'me failed')

    r = requests.get(BASE + '/users/me/sessions', headers=hdr)
    print('SESSIONS', r.status_code, r.text)
    must(r.status_code == 200, 'sessions failed')

    r = requests.post(BASE + '/auth/refresh', json={'refreshToken': ref})
    print('REFRESH', r.status_code, r.text)
    must(r.status_code == 200, 'refresh failed')
    print('PASS: smoke auth flow ok')

if __name__ == '__main__':
    main()
