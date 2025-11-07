-- Migration: Add is_active column to secretaries table
-- Purpose: Enable doctors to disable/enable secretary accounts

ALTER TABLE secretaries
ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL;

CREATE INDEX idx_secretaries_is_active ON secretaries(is_active);

-- Update all existing secretaries to active status
UPDATE secretaries SET is_active = TRUE WHERE is_active IS NULL;
