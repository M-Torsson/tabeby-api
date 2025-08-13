-- إضافة عمود كلمة المرور للموظفين لدعم تسجيل دخول الموظف بكلمة مرور مستقلة
ALTER TABLE staff ADD COLUMN IF NOT EXISTS password_hash TEXT;
