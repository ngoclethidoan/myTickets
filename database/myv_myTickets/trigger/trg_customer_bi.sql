DROP TRIGGER IF EXISTS trg_customer_bi;

DELIMITER $$

-- 1) One person cannot be both a customer and an admin. Admins live in another database
--    (myv_myTickets_admin), so we look into its admin table with the database.table syntax.
-- 2) Generate customer_id = 'CU' + running number (CU0001, CU0002, ...) when none is given.
CREATE TRIGGER trg_customer_bi
BEFORE INSERT ON customer
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF EXISTS (SELECT 1 FROM myv_myTickets_admin.admin WHERE username = NEW.username) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This username is already an admin and cannot also be a customer';
  END IF;

  IF NEW.customer_id IS NULL OR NEW.customer_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(customer_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM customer
     WHERE customer_id REGEXP '^CU[0-9]+$';

    SET NEW.customer_id = CONCAT('CU', LPAD(v_next, GREATEST(4, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
