DROP TRIGGER IF EXISTS trg_admin_bi;

DELIMITER $$

-- 1) ISA is disjoint: a user cannot be both an admin and a customer.
-- 2) Generate admin_id = 'AD' + running number (AD0001, AD0002, ...) when none is given.
CREATE TRIGGER trg_admin_bi
BEFORE INSERT ON admin
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF EXISTS (SELECT 1 FROM customer WHERE username = NEW.username) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This user is already a customer and cannot also be an admin';
  END IF;

  IF NEW.admin_id IS NULL OR NEW.admin_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(admin_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM admin
     WHERE admin_id REGEXP '^AD[0-9]+$';

    SET NEW.admin_id = CONCAT('AD', LPAD(v_next, GREATEST(4, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
