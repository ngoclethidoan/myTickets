DROP PROCEDURE IF EXISTS pc_pay_order;

DELIMITER $$

-- Finish payment of a pending order.
-- p_payment_success = 1: the order becomes 'paid' and is locked for good (no cancel, no change).
-- p_payment_success = 0: the order becomes 'failed'; trg_orders_au then releases its seats.
CREATE PROCEDURE pc_pay_order(
  IN p_order_id        VARCHAR(20),
  IN p_payment_success TINYINT(1)
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
    -- A ticket cannot be paid after its event has started
    IF EXISTS (SELECT 1
                 FROM ticket t
                 JOIN event e ON e.event_id = t.event_id
                WHERE t.order_id = p_order_id
                  AND NOW() >= e.start_time) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event has already started';
    END IF;

    UPDATE orders SET status = 'paid' WHERE order_id = p_order_id;
  ELSE
    UPDATE orders SET status = 'failed' WHERE order_id = p_order_id;
  END IF;

  COMMIT;
END$$

DELIMITER ;
