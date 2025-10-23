# 📱 Check Phone Number API

## Endpoint للتحقق من وجود رقم الهاتف قبل التسجيل

### ✅ **تم إنشاء Endpoint جديد:**

```
GET /auth/check-phone?phone={phone_number}
```

---

## 📋 **الوصف:**

يفحص إذا كان رقم الهاتف موجود في النظام ويرجع:
- ✅ إذا كان موجود: يرجع الـ **role** (patient/doctor/secretary)
- ❌ إذا لم يكن موجود: يرجع رسالة أن الرقم غير مسجل

---

## 🔧 **الاستخدام:**

### **Request:**
```http
GET https://tabeby-api.onrender.com/auth/check-phone?phone=%2B9647701234567
```

**ملاحظة:** يجب URL encode للـ `+` → `%2B`

---

## 📤 **Response Examples:**

### **1. رقم موجود (doctor):**
```json
{
  "exists": true,
  "phone_number": "+96407702928764",
  "user_role": "doctor",
  "user_server_id": 1,
  "user_uid": "s8r97394Fgolfk35fks",
  "message": "رقم الهاتف موجود مسبقاً كـ doctor"
}
```

### **2. رقم موجود (patient):**
```json
{
  "exists": true,
  "phone_number": "+9647701234567",
  "user_role": "patient",
  "user_server_id": 42,
  "user_uid": "firebase-uid-123",
  "message": "رقم الهاتف موجود مسبقاً كـ patient"
}
```

### **3. رقم غير موجود:**
```json
{
  "exists": false,
  "phone_number": "+9647709999999",
  "message": "رقم الهاتف غير مسجل في النظام"
}
```

---

## ❌ **Error Responses:**

### **1. بدون phone parameter:**
```json
{
  "error": {
    "code": "bad_request",
    "message": "phone parameter is required"
  }
}
```
**Status:** `400`

### **2. صيغة خاطئة (ليس E.164):**
```json
{
  "error": {
    "code": "invalid_format",
    "message": "phone must be in E.164 format (e.g., +9647701234567)"
  }
}
```
**Status:** `400`

---

## 🧪 **أمثلة الاستخدام:**

### **Flutter/Dart:**
```dart
Future<Map<String, dynamic>> checkPhoneExists(String phone) async {
  // تأكد من صيغة E.164
  if (!phone.startsWith('+')) {
    phone = '+964$phone'; // أضف كود العراق افتراضياً
  }
  
  final encodedPhone = Uri.encodeComponent(phone);
  final url = 'https://tabeby-api.onrender.com/auth/check-phone?phone=$encodedPhone';
  
  final response = await http.get(Uri.parse(url));
  
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to check phone');
  }
}

// الاستخدام:
void handlePhoneCheck() async {
  try {
    final result = await checkPhoneExists('+9647701234567');
    
    if (result['exists'] == true) {
      print('الرقم موجود مسبقاً كـ: ${result['user_role']}');
      // عرض رسالة للمستخدم
      showDialog(...);
    } else {
      print('الرقم متاح للتسجيل');
      // متابعة عملية التسجيل
      proceedToRegistration();
    }
  } catch (e) {
    print('خطأ: $e');
  }
}
```

### **JavaScript/Axios:**
```javascript
async function checkPhoneExists(phone) {
  try {
    const encodedPhone = encodeURIComponent(phone);
    const response = await axios.get(
      `https://tabeby-api.onrender.com/auth/check-phone?phone=${encodedPhone}`
    );
    
    if (response.data.exists) {
      console.log(`الرقم موجود كـ: ${response.data.user_role}`);
      return {
        exists: true,
        role: response.data.user_role,
        userId: response.data.user_server_id
      };
    } else {
      console.log('الرقم متاح للتسجيل');
      return { exists: false };
    }
  } catch (error) {
    console.error('خطأ:', error.response?.data);
    throw error;
  }
}
```

### **Python/Requests:**
```python
import requests
from urllib.parse import quote

def check_phone_exists(phone: str) -> dict:
    encoded_phone = quote(phone)
    url = f"https://tabeby-api.onrender.com/auth/check-phone?phone={encoded_phone}"
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        if data['exists']:
            print(f"الرقم موجود كـ: {data['user_role']}")
        else:
            print("الرقم متاح للتسجيل")
        return data
    else:
        print(f"خطأ: {response.json()}")
        return None

# مثال
result = check_phone_exists("+9647701234567")
```

---

## 🎯 **حالات الاستخدام:**

### **1. قبل التسجيل عبر Firebase:**
```dart
// في صفحة التسجيل
onPressed: () async {
  final phone = phoneController.text;
  final checkResult = await checkPhoneExists(phone);
  
  if (checkResult['exists']) {
    // الرقم موجود مسبقاً
    showAlertDialog(
      'تنبيه',
      'هذا الرقم مسجل مسبقاً كـ ${checkResult['user_role']}'
    );
  } else {
    // متابعة عملية Firebase Authentication
    await FirebaseAuth.instance.verifyPhoneNumber(
      phoneNumber: phone,
      // ...
    );
  }
}
```

### **2. التحقق من الدور قبل الدخول:**
```dart
// بعد Firebase login ناجح
final user = FirebaseAuth.instance.currentUser;
final phone = user?.phoneNumber;

final checkResult = await checkPhoneExists(phone!);

if (checkResult['user_role'] == 'doctor') {
  // انتقل لواجهة الدكتور
  Navigator.push(context, DoctorDashboard());
} else if (checkResult['user_role'] == 'patient') {
  // انتقل لواجهة المريض
  Navigator.push(context, PatientDashboard());
}
```

---

## ✨ **مميزات الـ API:**

- ✅ **يدعم الأرقام العربية** - يحولها تلقائياً لـ ASCII
- ✅ **التحقق من صيغة E.164** - يرفض الأرقام الخاطئة
- ✅ **سريع** - استعلام مباشر من قاعدة البيانات
- ✅ **آمن** - لا يتطلب authentication
- ✅ **واضح** - رسائل خطأ مفهومة بالعربي

---

## 📌 **ملاحظات:**

1. **صيغة الرقم:** يجب أن يكون بصيغة E.164 (`+` + كود الدولة + الرقم)
   - ✅ `+9647701234567`
   - ❌ `07701234567`
   - ❌ `9647701234567`

2. **URL Encoding:** تأكد من عمل encode للـ `+` عند الإرسال في URL
   - `+` → `%2B`

3. **يبحث في:** جدول `user_accounts` فقط
   - إذا كان الدكتور مسجل في جدول `doctors` فقط بدون `user_accounts`، لن يظهر

4. **لا يتطلب authentication** - API مفتوح للاستخدام

---

## 🚀 **جاهز للاستخدام الآن!**

```bash
# اختبار سريع
curl "https://tabeby-api.onrender.com/auth/check-phone?phone=%2B9647701234567"
```
