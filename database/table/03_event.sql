CREATE TABLE IF NOT EXISTS event (
  event_id          VARCHAR(20)  NOT NULL,
  venue_id          VARCHAR(20)  NOT NULL,
  event_name        VARCHAR(150) NOT NULL,
  artist            VARCHAR(150) NULL,
  sale_time         DATETIME     NOT NULL,
  start_time        DATETIME     NOT NULL,
  standing_capacity INT          NOT NULL DEFAULT 0,
  PRIMARY KEY (event_id),
  CONSTRAINT fk_event_venue FOREIGN KEY (venue_id) REFERENCES venue (venue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
