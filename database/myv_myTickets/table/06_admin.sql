-- Subtype of user (ISA). Admin has no extra attributes in the ERD.
CREATE TABLE IF NOT EXISTS admin (
  admin_id VARCHAR(20) NOT NULL,
  username VARCHAR(50) NOT NULL,
  PRIMARY KEY (admin_id),
  UNIQUE KEY uq_admin_username (username),
  CONSTRAINT fk_admin_user FOREIGN KEY (username) REFERENCES `user` (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
