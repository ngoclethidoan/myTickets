DROP PROCEDURE IF EXISTS pc_update_customer;

DELIMITER $$

-- Change the profile of a customer: name, email, phone number and (optionally) the password.
-- The customer_app account has no UPDATE right on the customer table, so this procedure is
-- the only way the web app can change a profile.
--   p_password  the NEW password hash, or NULL to keep the current password.
--               The web app checks the current password before it calls this procedure.
--   p_phone_num NULL or '' removes the phone number.
-- customer_id and username never change. A duplicate email is rejected by uq_customer_email.
CREATE PROCEDURE pc_update_customer(
  IN p_customer_id VARCHAR(20),
  IN p_name        VARCHAR(100),
  IN p_email       VARCHAR(100),
  IN p_phone_num   VARCHAR(20),
  IN p_password    VARCHAR(255)
)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM customer WHERE customer_id = p_customer_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Customer not found';
  END IF;
  IF p_name IS NULL OR TRIM(p_name) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Full name is required';
  END IF;
  IF p_email IS NULL OR p_email NOT LIKE '_%@_%' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A valid email address is required';
  END IF;
  IF p_password IS NOT NULL AND p_password = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The password cannot be empty';
  END IF;

  UPDATE customer
     SET name      = TRIM(p_name),
         email     = TRIM(p_email),
         phone_num = NULLIF(TRIM(COALESCE(p_phone_num, '')), ''),
         password  = COALESCE(p_password, password)
   WHERE customer_id = p_customer_id;
END$$

DELIMITER ;
