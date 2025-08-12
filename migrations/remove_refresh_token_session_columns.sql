-- حذف أعمدة الجلسة غير الموجودة من جدول refresh_tokens
ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS device;
ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS ip;
ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS user_agent;
ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS last_seen;
