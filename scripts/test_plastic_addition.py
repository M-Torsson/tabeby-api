import os
import json
from fastapi.testclient import TestClient

# Ensure env vars for DB and secret
os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///./local.db"))
os.environ.setdefault("DOCTOR_PROFILE_SECRET", "devsecret")

from app.main import app

c = TestClient(app)

# Create/update doctor profile via new contract
payload = {
  "phone": "+46765588443",
  "json_profile": {
    "general_info": {
      "clinic_id": 9,
      "doctor_name": "دارين مصطفى",
      "email_address": "dareen@gmail.com",
      "doctor_phone_number": "+46765588443",
      "gender": "امرأة",
      "about_doctor_bio": "اول دكتورة بالعالم",
      "license_number": "365485",
      "experience_years": "12",
      "number_patients_treated": "6500",
      "examination_fees": "50000",
      "receiving_patients": "55",
      "account_status": False,
      "profile_image_URL": "https://example.com/profile.jpg",
      "create_date": "2025-09-15 17:13:48.782993",
      "clinic_state": "بغداد",
      "clinic_states": "بغداد",
      "governorate": "بغداد",
      "clinic_address": "حي المنصور شارع الراشديات",
      "clinic_name": "الابتسامه المشرقه"
    },
    "specializations": [
      {"id": 1, "name": "جراحة تجميلية"},
      {"id": 2, "name": "بوتكس"},
      {"id": 3, "name": "فيلر"},
      {"id": 4, "name": "شفط ولفط ونفخ"},
      {"id": 5, "name": "تصغير تكبير"}
    ],
    "dents_addition": [],
    "plastic_addition": []
  }
}

r = c.post('/doctor/profile', json=payload)
print('POST /doctor/profile', r.status_code, r.json())

# Fetch via protected API endpoint which derives additions
hdr = {"Doctor-Secret": os.environ.get("DOCTOR_PROFILE_SECRET")}
r2 = c.get('/api/doctors/9', headers=hdr)
print('GET /api/doctors/9', r2.status_code)
print(json.dumps(r2.json(), ensure_ascii=False))

prof = r2.json().get('profile', {})
print('specializations:', prof.get('specializations'))
print('plastic_addition:', prof.get('plastic_addition'))
