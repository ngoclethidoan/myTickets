DROP FUNCTION IF EXISTS fn_order_hold_minutes;

DELIMITER $$

-- How many minutes a customer has to pay a pending order before it expires.
-- The single place where this number is defined in the database.
-- (The web app shows the same number on the orders page: ORDER_HOLD_MINUTES in app.py.)
CREATE FUNCTION fn_order_hold_minutes()
RETURNS INT
DETERMINISTIC
BEGIN
  RETURN 15;
END$$

DELIMITER ;
