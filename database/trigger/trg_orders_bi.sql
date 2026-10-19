DROP TRIGGER IF EXISTS trg_orders_bi;

DELIMITER $$

-- Generate order_id = 'OD' + running number (OD0001, OD0002, ...) when none is given
CREATE TRIGGER trg_orders_bi
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF NEW.order_id IS NULL OR NEW.order_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(order_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM orders
     WHERE order_id REGEXP '^OD[0-9]+$';

    SET NEW.order_id = CONCAT('OD', LPAD(v_next, GREATEST(4, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
