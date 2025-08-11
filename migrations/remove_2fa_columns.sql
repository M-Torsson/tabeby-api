-- حذف أعمدة 2FA والتفضيلات من جدول admins إن وُجدت
ALTER TABLE admins DROP COLUMN IF EXISTS two_factor_secret;
ALTER TABLE admins DROP COLUMN IF EXISTS two_factor_enabled;
ALTER TABLE admins DROP COLUMN IF EXISTS email_security_alerts;
ALTER TABLE admins DROP COLUMN IF EXISTS push_login_alerts;
ALTER TABLE admins DROP COLUMN IF EXISTS critical_only;
