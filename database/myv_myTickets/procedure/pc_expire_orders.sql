DROP PROCEDURE IF EXISTS pc_expire_orders;

DELIMITER $$

-- Fail every pending order that has been waiting longer than fn_order_hold_minutes().
-- trg_orders_au then deletes the tickets (and orphaned STANDING seats), so the seats become free again.
-- Paid and already failed orders are never touched.
--   p_expired (OUT)  how many orders were expired
-- Called every minute by the event ev_expire_orders, and at the start of pc_book_tickets
-- (so seats are released even if the scheduler is switched off).
-- No account except the owner is granted EXECUTE on it, so the web app cannot call it.
CREATE PROCEDURE pc_expire_orders(
  OUT p_expired INT
)
BEGIN
  UPDATE orders
     SET status = 'failed'
   WHERE status = 'pending'
     AND place_at < NOW() - INTERVAL fn_order_hold_minutes() MINUTE;

  SET p_expired = ROW_COUNT();
END$$

DELIMITER ;
