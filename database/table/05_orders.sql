CREATE TABLE IF NOT EXISTS orders (
  order_id    VARCHAR(20) NOT NULL,
  customer_id VARCHAR(20) NOT NULL,
  status      ENUM('pending', 'paid', 'failed') NOT NULL DEFAULT 'pending',
  PRIMARY KEY (order_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
