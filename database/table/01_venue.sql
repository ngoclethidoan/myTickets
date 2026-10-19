CREATE TABLE IF NOT EXISTS venue (
  venue_id VARCHAR(20)  NOT NULL,
  address  VARCHAR(255) NOT NULL,
  capacity INT          NOT NULL,
  PRIMARY KEY (venue_id),
  CONSTRAINT chk_venue_capacity CHECK (capacity > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
