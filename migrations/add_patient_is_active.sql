-- Add is_active column to patient_profiles table
-- This allows admins to activate/deactivate patient accounts

ALTER TABLE patient_profiles 
ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Add index for faster queries by status
CREATE INDEX ix_patient_profiles_is_active ON patient_profiles(is_active);

-- Comment for documentation
COMMENT ON COLUMN patient_profiles.is_active IS 'حالة تفعيل المريض - true للتفعيل، false للإيقاف';
