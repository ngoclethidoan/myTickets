DROP PROCEDURE IF EXISTS pc_pay_order;

DELIMITER $$

-- Finish payment of a pending order.
-- p_payment_success = 1: the payment method and date are stored on every ticket of the order (the `buy`
--                        attributes), then the order becomes 'paid' and is locked for good (no cancel, no change).
-- p_payment_success = 0: the order becomes 'failed'; trg_orders_au then releases its seats.
--                        p_pay_method is ignored in that case and may be NULL.
CREATE PROCEDURE pc_pay_order(
  IN p_order_id        VARCHAR(20),
  IN p_payment_success TINYINT(1),
  IN p_pay_method      VARCHAR(30)
)
BEGIN
  DECLARE v_status     VARCHAR(10);
  DECLARE v_ticket_cnt INT;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;

  -- Lock the order row so two payments cannot run at the same time
  SELECT status INTO v_status FROM orders WHERE order_id = p_order_id FOR UPDATE;

  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order not found';
  END IF;
  IF v_status <> 'pending' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only pending orders can be paid';
  END IF;

  SELECT COUNT(*) INTO v_ticket_cnt FROM ticket WHERE order_id = p_order_id;
  IF v_ticket_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order has no tickets';
  END IF;

  IF p_payment_success = 1 THEN
    IF p_pay_method IS NULL OR p_pay_method = '' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Payment method is required';
    END IF;

    -- A ticket cannot be paid after its event has started
    IF EXISTS (SELECT 1
                 FROM ticket t
                 JOIN event e ON e.event_id = t.event_id
                WHERE t.order_id = p_order_id
                  AND NOW() >= e.start_time) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event has already started';
    END IF;

    -- Store the payment details first: tickets are locked as soon as the order is 'paid'
    UPDATE ticket
       SET pay_method = p_pay_method,
           pay_date   = NOW()
     WHERE order_id = p_order_id;

    UPDATE orders SET status = 'paid' WHERE order_id = p_order_id;
  ELSE
    UPDATE orders SET status = 'failed' WHERE order_id = p_order_id;
  END IF;

  COMMIT;
END$$

DELIMITER ;
