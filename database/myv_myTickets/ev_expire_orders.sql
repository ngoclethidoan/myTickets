DROP EVENT IF EXISTS ev_expire_orders;

DELIMITER $$

-- Scheduled job: every minute, fail the pending orders that were not paid in time.
-- Needs the MySQL event scheduler to be ON:  SHOW VARIABLES LIKE 'event_scheduler';
CREATE EVENT ev_expire_orders
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN
  CALL pc_expire_orders(@expired_orders);
END$$

DELIMITER ;
