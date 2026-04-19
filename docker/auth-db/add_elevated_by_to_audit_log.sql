ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS elevated_by VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_audit_log_elevated_by ON audit_log(elevated_by);
