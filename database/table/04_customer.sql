CREATE TABLE IF NOT EXISTS customer (
  customer_id VARCHAR(20)  NOT NULL,
  full_name   VARCHAR(100) NOT NULL,
  email       VARCHAR(100) NOT NULL,
  phone       VARCHAR(20)  NULL,
  PRIMARY KEY (customer_id),
  UNIQUE KEY uq_customer_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
