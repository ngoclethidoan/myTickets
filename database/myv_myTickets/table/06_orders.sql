-- customer --place--> orders (1-N). place_at is the attribute of `place`.
CREATE TABLE IF NOT EXISTS orders (
  order_id    VARCHAR(20) NOT NULL,
  customer_id VARCHAR(20) NOT NULL,
  place_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status      ENUM('pending', 'paid', 'failed') NOT NULL DEFAULT 'pending',
  PRIMARY KEY (order_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
