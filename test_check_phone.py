#!/usr/bin/env python3
"""
Test the new /auth/check-phone endpoint
"""
import os
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 70)
print("🧪 Testing /auth/check-phone Endpoint")
print("=" * 70)

# Test 1: رقم غير موجود
print("\n[Test 1] Check non-existent phone")
r1 = client.get("/auth/check-phone?phone=%2B9647709999999")
print(f"Status: {r1.status_code}")
print(f"Response: {r1.json()}")

# Test 2: بدون phone parameter
print("\n[Test 2] Missing phone parameter")
r2 = client.get("/auth/check-phone")
print(f"Status: {r2.status_code}")
print(f"Response: {r2.json()}")

# Test 3: صيغة خاطئة
print("\n[Test 3] Invalid phone format (no +)")
r3 = client.get("/auth/check-phone?phone=9647701234567")
print(f"Status: {r3.status_code}")
print(f"Response: {r3.json()}")

# Test 4: تسجيل رقم جديد
print("\n[Test 4] Register a new phone number")
test_phone = "+964770TEST123"
r4 = client.post("/auth/register", json={
    "phone_number": test_phone,
    "user_role": "patient",
    "user_uid": "test-uid-123"
})
print(f"Status: {r4.status_code}")
print(f"Response: {r4.json()}")

# Test 5: فحص الرقم المسجل
print("\n[Test 5] Check the registered phone")
r5 = client.get(f"/auth/check-phone?phone={test_phone}")
print(f"Status: {r5.status_code}")
print(f"Response: {r5.json()}")

# Test 6: رقم بأرقام عربية
print("\n[Test 6] Phone with Arabic digits")
r6 = client.get("/auth/check-phone?phone=%2B٩٦٤٧٧٠١٢٣٤٥٦٧")
print(f"Status: {r6.status_code}")
print(f"Response: {r6.json()}")

print("\n" + "=" * 70)
print("✅ All tests completed!")
print("=" * 70)
