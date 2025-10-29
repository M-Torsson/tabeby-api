"""
Golden Payments Manual Testing Guide
=====================================

Requirements:
1. Database must have golden_payments table (run migration first)
2. Set DOCTOR_PROFILE_SECRET environment variable
3. Server must be running on http://localhost:8000

Test using curl or Postman with the following requests:
"""

import json

# Configuration
BASE_URL = "http://localhost:8000"
SECRET = "your-secret-here"  # Replace with actual secret

print("="*70)
print("Golden Payments API Testing Guide")
print("="*70)

# Test 1: Create payment record
print("\n[Test 1] POST /api/golden_patient_payment")
print("Request:")
test1 = {
    "url": f"{BASE_URL}/api/golden_patient_payment",
    "method": "POST",
    "headers": {"Doctor-Secret": SECRET},
    "body": {
        "clinic_id": 4,
        "exam_date": "23/10/2025",
        "book_status": "تمت المعاينة",
        "patient_name": "عمر احمد",
        "booking_id": "G-4-20251023-P-71",
        "code": "6270"
    }
}
print(json.dumps(test1, indent=2, ensure_ascii=False))

# Test 2: Get monthly status
print("\n[Test 2] GET /api/doctor_monthly_golden_payment_status")
print("Request:")
test2 = {
    "url": f"{BASE_URL}/api/doctor_monthly_golden_payment_status?clinic_id=4",
    "method": "GET",
    "headers": {"Doctor-Secret": SECRET}
}
print(json.dumps(test2, indent=2, ensure_ascii=False))

# Test 3: Get annual status
print("\n[Test 3] GET /api/doctor_annual_payment_status")
print("Request:")
test3 = {
    "url": f"{BASE_URL}/api/doctor_annual_payment_status?clinic_id=4",
    "method": "GET",
    "headers": {"Doctor-Secret": SECRET}
}
print(json.dumps(test3, indent=2, ensure_ascii=False))

# Test 4: Update payment status
print("\n[Test 4] POST /api/update_payment_status")
print("Request:")
test4 = {
    "url": f"{BASE_URL}/api/update_payment_status",
    "method": "POST",
    "headers": {"Doctor-Secret": SECRET},
    "body": {
        "clinic_id": 4,
        "payment_month": "2025-10",
        "payment_status": "paid"
    }
}
print(json.dumps(test4, indent=2, ensure_ascii=False))

print("\n" + "="*70)
print("CURL Commands:")
print("="*70)

print("\n# Test 1: Create payment")
print(f'''curl -X POST "{BASE_URL}/api/golden_patient_payment" \\
  -H "Doctor-Secret: {SECRET}" \\
  -H "Content-Type: application/json" \\
  -d '{{"clinic_id":4,"exam_date":"23/10/2025","book_status":"تمت المعاينة","patient_name":"عمر احمد","booking_id":"G-4-20251023-P-71","code":"6270"}}'
''')

print("\n# Test 2: Get monthly status")
print(f'''curl -X GET "{BASE_URL}/api/doctor_monthly_golden_payment_status?clinic_id=4" \\
  -H "Doctor-Secret: {SECRET}"
''')

print("\n# Test 3: Get annual status")
print(f'''curl -X GET "{BASE_URL}/api/doctor_annual_payment_status?clinic_id=4" \\
  -H "Doctor-Secret: {SECRET}"
''')

print("\n# Test 4: Update payment status")
print(f'''curl -X POST "{BASE_URL}/api/update_payment_status" \\
  -H "Doctor-Secret: {SECRET}" \\
  -H "Content-Type: application/json" \\
  -d '{{"clinic_id":4,"payment_month":"2025-10","payment_status":"paid"}}'
''')

print("\n" + "="*70)
print("Expected Responses:")
print("="*70)

print("\n[Test 1 Response] Status 200:")
print(json.dumps({
    "message": "تم حفظ الدفعة بنجاح",
    "booking_id": "G-4-20251023-P-71",
    "patient_name": "عمر احمد",
    "amount": 1500,
    "payment_month": "2025-10",
    "payment_status": "not_paid"
}, indent=2, ensure_ascii=False))

print("\n[Test 2 Response] Status 200:")
print(json.dumps({
    "2025-10": {
        "payment_month": "2025-10",
        "patient_count": 1,
        "total_amount": 1500,
        "payment_status": "not_paid",
        "patients": [
            {
                "patient_name": "عمر احمد",
                "exam_date": "23/10/2025",
                "amount": 1500
            }
        ]
    }
}, indent=2, ensure_ascii=False))

print("\n[Test 3 Response] Status 200:")
print(json.dumps({
    "clinic_id": 4,
    "year": 2025,
    "total_paid": 0,
    "remain_amount": 1500,
    "months": {
        "2025-10": "not_paid"
    }
}, indent=2, ensure_ascii=False))

print("\n[Test 4 Response] Status 200:")
print(json.dumps({
    "message": "تم تحديث حالة الدفع بنجاح",
    "clinic_id": 4,
    "payment_month": "2025-10",
    "payment_status": "paid",
    "updated_count": 1
}, indent=2, ensure_ascii=False))

print("\n" + "="*70)
