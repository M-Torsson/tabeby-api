-- إضافة جدول لتتبع حالة العيادات (مفتوحة/مغلقة)
CREATE TABLE IF NOT EXISTS clinic_status (
    id SERIAL PRIMARY KEY,
    clinic_id INTEGER UNIQUE NOT NULL,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- إنشاء index على clinic_id للبحث السريع
CREATE INDEX IF NOT EXISTS ix_clinic_status_clinic_id ON clinic_status (clinic_id);

-- إضافة تعليق للجدول
COMMENT ON TABLE clinic_status IS 'يخزن حالة العيادات (مفتوحة أو مغلقة)';
COMMENT ON COLUMN clinic_status.clinic_id IS 'معرف العيادة (فريد)';
COMMENT ON COLUMN clinic_status.is_closed IS 'هل العيادة مغلقة؟ (true = مغلقة, false = مفتوحة)';
