DROP TRIGGER IF EXISTS trg_ticket_bi;

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

  -- Load event info
  SELECT venue_id, sale_time, start_time, standing_capacity
    INTO v_venue_event, v_sale, v_start, v_stand_cap
    FROM event WHERE event_id = NEW.event_id;

  -- Check: tickets can only be sold between sale_time and start_time
  IF NOW() < v_sale OR NOW() >= v_start THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ticket sales are not open for this event';
  END IF;

  -- Check: tickets can only be added to a pending order (paid orders are locked)
  SELECT customer_id, status INTO v_customer, v_status
    FROM orders WHERE order_id = NEW.order_id;
  IF v_status <> 'pending' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Tickets can only be added to a pending order';
  END IF;

  -- buy: the customer of the ticket is the customer who placed the order
  IF NEW.customer_id IS NULL THEN
    SET NEW.customer_id = v_customer;
  ELSEIF NEW.customer_id <> v_customer THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ticket customer must be the customer of the order';
  END IF;

  -- Payment details are filled in only by pc_pay_order, when the order is paid
  IF NEW.pay_method IS NOT NULL OR NEW.pay_date IS NOT NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payment details are set when the order is paid';
  END IF;

  -- Resolve zone: NULL seat_id means a standing ticket
  IF NEW.seat_id IS NULL THEN
    SET v_zone = 'STANDING';
  ELSE
    SELECT seat_zone, venue_id INTO v_zone, v_seat_venue
      FROM seat WHERE seat_id = NEW.seat_id;
    -- Check: the seat must belong to the venue hosting the event
    IF v_seat_venue <> v_venue_event THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Seat is not in the right venue!';
    END IF;
  END IF;

  -- Check: max 2 tickets of the same zone per event per customer (pending + paid orders)
  SELECT COUNT(*) INTO v_cnt
    FROM ticket t
    JOIN orders o ON o.order_id = t.order_id
    JOIN seat   s ON s.seat_id  = t.seat_id
   WHERE o.customer_id = v_customer
     AND t.event_id    = NEW.event_id
     AND s.seat_zone   = v_zone
     AND o.status IN ('pending', 'paid');
  IF v_cnt >= 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Maximum 2 tickets of the same type per event';
  END IF;

  -- Check: one order can only contain one seat_zone
  SELECT COUNT(*) INTO v_cnt
    FROM ticket t
    JOIN seat s ON s.seat_id = t.seat_id
   WHERE t.order_id = NEW.order_id
     AND s.seat_zone <> v_zone;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'One order can only contain one ticket type';
  END IF;
	
  -- Standing ticket: check capacity, generate id, insert virtual seat (done last)
  IF NEW.seat_id IS NULL THEN
    IF COALESCE(v_stand_cap, 0) <= 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This event has no standing area';
    END IF;

    SELECT COUNT(*) INTO v_cnt
      FROM ticket t
      JOIN seat s ON s.seat_id = t.seat_id
     WHERE t.event_id = NEW.event_id AND s.seat_zone = 'STANDING';
    IF v_cnt >= v_stand_cap THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Out of capacity!';
    END IF;

    -- Order number = current max + 1 (not COUNT, because rows may be deleted)
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
