-- Supertype of the ISA: every customer and every admin is a user.
-- `user` is written with backticks because USER is also an SQL keyword.
CREATE TABLE IF NOT EXISTS `user` (
  username VARCHAR(50)  NOT NULL,
  password VARCHAR(255) NOT NULL,  -- store a hash of the password, never the plain text
  PRIMARY KEY (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
