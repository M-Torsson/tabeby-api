-- Migration: add booking_archives table
CREATE TABLE IF NOT EXISTS booking_archives (
    id SERIAL PRIMARY KEY,
    clinic_id INTEGER NOT NULL,
    table_date VARCHAR(20) NOT NULL,
    capacity_total INTEGER NOT NULL,
    capacity_served INTEGER NULL,
    capacity_cancelled INTEGER NULL,
    patients_json TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW()),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW())
);

CREATE INDEX IF NOT EXISTS ix_booking_archives_clinic_date ON booking_archives (clinic_id, table_date);
