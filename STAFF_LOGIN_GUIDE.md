# دليل تسجيل دخول الموظفين (Staff Login)

## الوضع الحالي ✅

النظام **جاهز تماماً** لتسجيل دخول الموظفين! كل شيء موجود:

### 1️⃣ API تسجيل الدخول موجود:
```
POST /staff/login
```

### 2️⃣ Migration موجود:
```sql
-- migrations/add_staff_password_hash.sql
ALTER TABLE staff ADD COLUMN IF NOT EXISTS password_hash TEXT;
```

### 3️⃣ عند إنشاء Staff جديد:
- يتم حفظ `password_hash` تلقائياً
- يصير يقدر يسجل دخول مباشرة

---

## الخطوة المطلوبة فقط ⚠️

**تشغيل الـ Migration على قاعدة البيانات:**

```bash
psql -U postgres -d tabeby_db -f migrations/add_staff_password_hash.sql
```

---

## كيفية الاستخدام 

### 1. إنشاء موظف جديد (Admin/Staff بصلاحية):

**POST** `/staff`

```json
{
  "email": "staff@example.com",
  "password": "SecurePassword123",
  "name": "اسم الموظف"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "اسم الموظف",
  "email": "staff@example.com",
  "role": "staff",
  "status": "active"
}
```

---

### 2. تسجيل دخول الموظف:

**POST** `/staff/login`

```json
{
  "email": "staff@example.com",
  "password": "SecurePassword123"
}
```

**Response:**
```json
{
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "tokenType": "bearer",
    "user": {
      "id": 1,
      "name": "اسم الموظف",
      "email": "staff@example.com",
      "role": "staff"
    }
  }
}
```

---

### 3. استخدام الـ Token:

بعد تسجيل الدخول، استخدم الـ `accessToken` في الـ header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

---

## الأدوار المتاحة

عند إنشاء staff، يمكن تحديد الدور:

```json
{
  "email": "admin@clinic.com",
  "password": "pass123",
  "role": "admin"
}
```

**الأدوار الافتراضية:**
- `staff` - موظف عادي
- `admin` - إداري
- `manager` - مدير
- `secretary` - سكرتير

---

## CURL Examples

### إنشاء موظف:
```bash
curl -X POST "http://localhost:8000/staff" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newstaff@clinic.com",
    "password": "MyPassword123",
    "name": "موظف جديد"
  }'
```

### تسجيل دخول موظف:
```bash
curl -X POST "http://localhost:8000/staff/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newstaff@clinic.com",
    "password": "MyPassword123"
  }'
```

---

## ملاحظات مهمة

1. ✅ **كلمة المرور محفوظة بشكل آمن**: يستخدم النظام `bcrypt` لتشفير كلمة المرور
2. ✅ **التحقق من الحالة**: يتأكد النظام أن الموظف `status = "active"`
3. ✅ **البريد فريد**: لا يمكن تكرار نفس البريد الإلكتروني
4. ✅ **Token متوافق**: الـ token من نوع `staff` ويعمل مع باقي الـ APIs

---

## التحقق من نجاح الـ Migration

بعد تشغيل الـ migration، تأكد:

```sql
-- تحقق من وجود العمود
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'staff' AND column_name = 'password_hash';
```

يجب أن تظهر:
```
 column_name  | data_type 
--------------+-----------
 password_hash| text
```

---

**كل شيء جاهز! فقط شغّل الـ Migration** 🚀
