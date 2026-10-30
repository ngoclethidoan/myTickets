DROP PROCEDURE IF EXISTS pc_book_tickets;

DELIMITER $$

-- Book 1 or 2 tickets of ONE seat zone for a customer. Creates a pending order and adds the tickets to it.
-- Real zones: the procedure picks the first free seats (ordered by row, then number).
-- STANDING zone: seat_id is passed as NULL and trg_ticket_bi creates the virtual seat.
-- p_ticket_price is the LIST price of one ticket. The customer's membership discount
-- (vw_customer_membership) is taken off here, and the discounted price is what is stored in the ticket.
-- Everything runs in one transaction: if any ticket fails, the order and all tickets are rolled back.
CREATE PROCEDURE pc_book_tickets(
  IN  p_customer_id  VARCHAR(20),
  IN  p_event_id     VARCHAR(20),
  IN  p_seat_zone    VARCHAR(20),
  IN  p_quantity     INT,
  IN  p_ticket_price DECIMAL(12,2),
  OUT p_order_id     VARCHAR(20)
)
BEGIN
  DECLARE v_venue_id    VARCHAR(20);
  DECLARE v_seat_id     VARCHAR(20);
  DECLARE v_is_standing TINYINT(1);
  DECLARE v_i           INT DEFAULT 0;
  DECLARE v_discount    INT DEFAULT 0;
  DECLARE v_price       DECIMAL(12,2);

  -- On any error: undo everything, then re-raise the original error to the caller
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_order_id = NULL;

  -- Validate input
  IF p_quantity IS NULL OR p_quantity NOT BETWEEN 1 AND 2 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity must be 1 or 2';
  END IF;
  IF p_seat_zone IS NULL OR p_ticket_price IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Seat zone and ticket price are required';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Customer not found';
  END IF;

  SELECT venue_id INTO v_venue_id FROM event WHERE event_id = p_event_id;
  IF v_venue_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event not found';
  END IF;

  SET v_is_standing = (p_seat_zone = 'STANDING');

  -- Membership discount of this customer (stays 0 when the customer has no rank row)
  SELECT discount_percent INTO v_discount FROM vw_customer_membership WHERE customer_id = p_customer_id;
  SET v_price = ROUND(p_ticket_price * (100 - COALESCE(v_discount, 0)) / 100, 0);

  START TRANSACTION;

  -- Create the pending order; trg_orders_bi generates order_id
  INSERT INTO orders (order_id, customer_id) VALUES (NULL, p_customer_id);

  -- Read back the generated id: the newest order of this customer
  SELECT order_id INTO p_order_id
    FROM orders
   WHERE customer_id = p_customer_id
   ORDER BY CAST(SUBSTRING(order_id, 3) AS UNSIGNED) DESC
   LIMIT 1;

  -- Add the tickets one by one; trg_ticket_bi enforces every business rule
  WHILE v_i < p_quantity DO
    SET v_seat_id = NULL;

    IF v_is_standing = 0 THEN
      -- First free seat of this zone in the event's venue
      SELECT s.seat_id INTO v_seat_id
        FROM seat s
       WHERE s.venue_id  = v_venue_id
         AND s.seat_zone = p_seat_zone
         AND NOT EXISTS (SELECT 1 FROM ticket t
                          WHERE t.seat_id = s.seat_id
                            AND t.event_id = p_event_id)
       ORDER BY s.seat_row, s.seat_number
       LIMIT 1;

      IF v_seat_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Not enough available seats in this zone';
      END IF;
    END IF;

    -- customer_id is the `buy` link: the ticket belongs to the customer who placed the order
    INSERT INTO ticket (seat_id, event_id, order_id, customer_id, ticket_price, is_standing)
    VALUES (v_seat_id, p_event_id, p_order_id, p_customer_id, v_price, v_is_standing);

    SET v_i = v_i + 1;
  END WHILE;

  COMMIT;
END$$

DELIMITER ;
