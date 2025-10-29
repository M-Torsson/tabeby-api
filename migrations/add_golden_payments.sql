-- Migration: Add golden_payments table
-- Date: 2025-10-29
-- Description: Store golden booking payments for monthly tracking

CREATE TABLE IF NOT EXISTS golden_payments (
    id SERIAL PRIMARY KEY,
    clinic_id INTEGER NOT NULL,
    booking_id VARCHAR(255) NOT NULL,
    patient_name VARCHAR(255) NOT NULL,
    code VARCHAR(4) NOT NULL,
    exam_date VARCHAR(20) NOT NULL,
    book_status VARCHAR(50) NOT NULL DEFAULT 'تمت المعاينة',
    amount INTEGER NOT NULL DEFAULT 1500,
    payment_month VARCHAR(7) NOT NULL,  -- Format: YYYY-MM (e.g., 2025-10)
    payment_status VARCHAR(20) NOT NULL DEFAULT 'not_paid',  -- not_paid, paid
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(booking_id)
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_golden_payments_clinic_month ON golden_payments(clinic_id, payment_month);
CREATE INDEX IF NOT EXISTS idx_golden_payments_status ON golden_payments(payment_status);
CREATE INDEX IF NOT EXISTS idx_golden_payments_booking ON golden_payments(booking_id);

-- Comments
COMMENT ON TABLE golden_payments IS 'Stores golden booking payments - 1500 IQD per patient';
COMMENT ON COLUMN golden_payments.payment_month IS 'Format: YYYY-MM for grouping by month';
COMMENT ON COLUMN golden_payments.amount IS 'Fixed at 1500 IQD per patient';
