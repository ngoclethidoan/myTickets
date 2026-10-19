DROP TRIGGER IF EXISTS trg_orders_bd;

DELIMITER $$

-- A paid order cannot be deleted
CREATE TRIGGER trg_orders_bd
BEFORE DELETE ON orders
FOR EACH ROW
BEGIN
  IF OLD.status = 'paid' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order is already paid and cannot be deleted';
  END IF;
END$$

DELIMITER ;
