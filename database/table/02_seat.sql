CREATE TABLE IF NOT EXISTS seat (
  seat_id     VARCHAR(20) NOT NULL,
  venue_id    VARCHAR(20) NOT NULL,
  seat_zone   VARCHAR(20) NOT NULL,
  seat_row    VARCHAR(10) NULL,
  seat_number INT         NULL,
  PRIMARY KEY (seat_id),
  -- Ghe that khong trung trong cung venue.
  -- Ghe ao STANDING co row/number NULL nen khong bi UNIQUE chan.
  UNIQUE KEY uq_seat_position (venue_id, seat_zone, seat_row, seat_number),
  CONSTRAINT fk_seat_venue FOREIGN KEY (venue_id) REFERENCES venue (venue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
