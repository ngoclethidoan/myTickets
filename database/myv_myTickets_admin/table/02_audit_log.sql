USE myv_myTickets_admin;

-- History of what admins did (for example: ADD_EVENT on EV07).
-- Rows are only added by admin procedures, never edited by hand.
CREATE TABLE IF NOT EXISTS audit_log (
  log_id    INT         NOT NULL AUTO_INCREMENT,
  admin_id  VARCHAR(20) NOT NULL,
  action    VARCHAR(30) NOT NULL,                                -- e.g. ADD_EVENT
  target_id VARCHAR(20) NULL,                                    -- id of the thing the action touched, e.g. EV07
  done_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_audit_admin (admin_id),
  CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES admin (admin_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
