-- Migration: add patient_profiles table
CREATE TABLE IF NOT EXISTS patient_profiles (
    id SERIAL PRIMARY KEY,
    user_account_id INTEGER NOT NULL UNIQUE REFERENCES user_accounts(id) ON DELETE CASCADE,
    patient_name VARCHAR NOT NULL,
    phone_number VARCHAR NOT NULL,
    gender VARCHAR NULL,
    date_of_birth VARCHAR NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW()),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW())
);

CREATE INDEX IF NOT EXISTS ix_patient_profiles_user ON patient_profiles (user_account_id);
CREATE INDEX IF NOT EXISTS ix_patient_profiles_phone ON patient_profiles (phone_number);
