-- Subtype of user (ISA). username links the customer to its user row.
CREATE TABLE IF NOT EXISTS customer (
  customer_id VARCHAR(20)  NOT NULL,
  username    VARCHAR(50)  NOT NULL,
  name        VARCHAR(100) NOT NULL,
  email       VARCHAR(100) NOT NULL,
  phone_num   VARCHAR(20)  NULL,
  PRIMARY KEY (customer_id),
  UNIQUE KEY uq_customer_username (username),
  UNIQUE KEY uq_customer_email (email),
  CONSTRAINT fk_customer_user FOREIGN KEY (username) REFERENCES `user` (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
