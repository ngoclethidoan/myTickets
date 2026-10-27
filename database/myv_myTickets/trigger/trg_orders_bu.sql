DROP TRIGGER IF EXISTS trg_orders_bu;

DELIMITER $$

-- paid and failed are final states; the customer of an order never changes
-- (tickets copy the customer from the order, so the two must stay equal)
CREATE TRIGGER trg_orders_bu
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
  IF OLD.status IN ('paid', 'failed') AND NEW.status <> OLD.status THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Order is in a final state and its status cannot be modified';
  END IF;
  IF NEW.customer_id <> OLD.customer_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The customer of an order cannot be changed';
  END IF;
END$$

DELIMITER ;
