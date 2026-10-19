DELIMITER $$

CREATE TRIGGER trg_ticket_bi
BEFORE INSERT ON ticket
FOR EACH ROW
BEGIN
  DECLARE v_venue_event VARCHAR(20);
  DECLARE v_sale        DATETIME;
  DECLARE v_start       DATETIME;
  DECLARE v_stand_cap   INT;
  DECLARE v_zone        VARCHAR(20);
  DECLARE v_seat_venue  VARCHAR(20);
  DECLARE v_customer    VARCHAR(20);
  DECLARE v_status      VARCHAR(10);
  DECLARE v_cnt         INT;
  DECLARE v_next        INT;

  -- Get event's info
  SELECT venue_id, sale_time, start_time, standing_capacity
    INTO v_venue_event, v_sale, v_start, v_stand_cap
    FROM event WHERE event_id = NEW.event_id;

  -- Check if event is on sale
  IF NOW() < v_sale OR NOW() >= v_start THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Sale is over!';
  END IF;

  -- Check if the tickets order is pending
  SELECT customer_id, status INTO v_customer, v_status
    FROM orders WHERE order_id = NEW.order_id;
  IF v_status <> 'pending' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order must be pending';
  END IF;

  -- Check zone: if is_standing
  IF NEW.seat_id IS NULL THEN
    SET v_zone = 'STANDING';
  ELSE
    SELECT seat_zone, venue_id INTO v_zone, v_seat_venue
      FROM seat WHERE seat_id = NEW.seat_id;
    -- 6. Ghế phải thuộc venue đang host event
    IF v_seat_venue <> v_venue_event THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Seat is not in the right venue!';
    END IF;
  END IF;

  -- Check: 1 customer/1 type/1 eent
  SELECT COUNT(*) INTO v_cnt
    FROM ticket t
    JOIN orders o ON o.order_id = t.order_id
    JOIN seat   s ON s.seat_id  = t.seat_id
   WHERE o.customer_id = v_customer
     AND t.event_id    = NEW.event_id
     AND s.seat_zone   = v_zone
     AND o.status IN ('pending', 'paid');
  IF v_cnt >= 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity exceeds limit!';
  END IF;

  -- Check: only 1 zone in 1 order
  SELECT COUNT(*) INTO v_cnt
    FROM ticket t
    JOIN seat s ON s.seat_id = t.seat_id
   WHERE t.order_id = NEW.order_id
     AND s.seat_zone <> v_zone;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Moi don chi chua mot loai ve';
  END IF;

  -- Check standing ticket: capacity, create id and add virtual seat
  IF NEW.seat_id IS NULL THEN
    IF COALESCE(v_stand_cap, 0) <= 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'There is no standing zone for this event!';
    END IF;

    SELECT COUNT(*) INTO v_cnt
      FROM ticket t
      JOIN seat s ON s.seat_id = t.seat_id
     WHERE t.event_id = NEW.event_id AND s.seat_zone = 'STANDING';
    IF v_cnt >= v_stand_cap THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Out of capacity!';
    END IF;

    ----- order number(stt) = MAX + 1
    SELECT COALESCE(MAX(CAST(SUBSTRING_INDEX(seat_id, '-', -1) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM seat
     WHERE seat_id LIKE CONCAT('STND-', NEW.event_id, '-%');

    SET NEW.seat_id = CONCAT('STND-', NEW.event_id, '-', LPAD(v_next, 4, '0'));

    INSERT INTO seat (seat_id, venue_id, seat_zone, seat_row, seat_number)
    VALUES (NEW.seat_id, v_venue_event, 'STANDING', NULL, NULL);
  END IF;
END$$

DELIMITER ;