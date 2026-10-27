DROP PROCEDURE IF EXISTS pc_cancel_order;

DELIMITER $$

-- Cancel an order that has NOT been paid yet.
-- A paid order can never be cancelled (also enforced by the triggers).
-- Cancelling sets the status to 'failed'; trg_orders_au then deletes the tickets
-- and the virtual STANDING seats, so the seats become available again.
-- The order row is kept as history.
CREATE PROCEDURE pc_cancel_order(
  IN p_order_id VARCHAR(20)
)
BEGIN
  DECLARE v_status VARCHAR(10);

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;

  SELECT status INTO v_status FROM orders WHERE order_id = p_order_id FOR UPDATE;

  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order not found';
  END IF;
  IF v_status = 'paid' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A paid order cannot be cancelled';
  END IF;
  IF v_status = 'failed' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order is already cancelled or failed';
  END IF;

  UPDATE orders SET status = 'failed' WHERE order_id = p_order_id;

  COMMIT;
END$$

DELIMITER ;
