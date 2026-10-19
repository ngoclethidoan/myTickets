DROP TRIGGER IF EXISTS trg_orders_bu;

DELIMITER $$

-- paid and failed are final states; a paid order cannot change its customer
CREATE TRIGGER trg_orders_bu
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
  IF OLD.status IN ('paid', 'failed') AND NEW.status <> OLD.status THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order is in a final state and its status cannot be changed';
  END IF;
  IF OLD.status = 'paid' AND NEW.customer_id <> OLD.customer_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order is already paid and cannot be modified';
  END IF;
END$$

DELIMITER ;
