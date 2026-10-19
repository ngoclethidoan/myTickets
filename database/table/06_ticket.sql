CREATE TABLE IF NOT EXISTS ticket (
  seat_id      VARCHAR(20)   NOT NULL,
  event_id     VARCHAR(20)   NOT NULL,
  order_id     VARCHAR(20)   NOT NULL,
  ticket_price DECIMAL(12,2) NOT NULL,
  is_standing  TINYINT(1)    NOT NULL DEFAULT 0,
  PRIMARY KEY (seat_id, event_id),
  CONSTRAINT fk_ticket_seat   FOREIGN KEY (seat_id)  REFERENCES seat (seat_id),
  CONSTRAINT fk_ticket_event  FOREIGN KEY (event_id) REFERENCES event (event_id),
  CONSTRAINT fk_ticket_orders FOREIGN KEY (order_id) REFERENCES orders (order_id),
  CONSTRAINT chk_ticket_price CHECK (ticket_price >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
