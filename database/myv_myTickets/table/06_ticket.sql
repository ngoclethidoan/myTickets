-- ticket: key = (seat_id, event_id).
-- order_id    comes from `contain` (orders 1-N ticket)
-- customer_id comes from `buy`     (customer 1-N ticket); trg_ticket_bi keeps it equal to the order's customer
-- pay_method, pay_date are the attributes of `buy`; they stay NULL until pc_pay_order pays the order
CREATE TABLE IF NOT EXISTS ticket (
  seat_id      VARCHAR(20)   NOT NULL,
  event_id     VARCHAR(20)   NOT NULL,
  order_id     VARCHAR(20)   NOT NULL,
  customer_id  VARCHAR(20)   NOT NULL,
  ticket_price DECIMAL(12,2) NOT NULL,
  is_standing  TINYINT(1)    NOT NULL DEFAULT 0,
  pay_method   VARCHAR(30)   NULL,
  pay_date     DATETIME      NULL,
  PRIMARY KEY (seat_id, event_id),
  CONSTRAINT fk_ticket_seat     FOREIGN KEY (seat_id)     REFERENCES seat (seat_id),
  CONSTRAINT fk_ticket_event    FOREIGN KEY (event_id)    REFERENCES event (event_id),
  CONSTRAINT fk_ticket_orders   FOREIGN KEY (order_id)    REFERENCES orders (order_id),
  CONSTRAINT fk_ticket_customer FOREIGN KEY (customer_id) REFERENCES customer (customer_id),
  CONSTRAINT chk_ticket_price   CHECK (ticket_price >= 0),
  CONSTRAINT chk_ticket_pay     CHECK ((pay_method IS NULL AND pay_date IS NULL)
                                    OR (pay_method IS NOT NULL AND pay_date IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
