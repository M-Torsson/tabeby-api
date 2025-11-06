-- إضافة جدول وضع الصيانة للتطبيق
-- App Maintenance Mode Table

CREATE TABLE IF NOT EXISTS app_maintenance (
    id SERIAL PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    message_ar TEXT,
    message_en TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

-- إنشاء فهرس على حالة الصيانة للسرعة
CREATE INDEX IF NOT EXISTS idx_app_maintenance_is_active ON app_maintenance(is_active);

-- إدراج سجل افتراضي (غير نشط)
INSERT INTO app_maintenance (is_active, message_ar, message_en)
VALUES (
    FALSE,
    'التطبيق تحت الصيانة، نعتذر عن الإزعاج',
    'App is under maintenance, sorry for the inconvenience'
)
ON CONFLICT DO NOTHING;

-- تعليق: يجب أن يكون هناك سجل واحد فقط في هذا الجدول
