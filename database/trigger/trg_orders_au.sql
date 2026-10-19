DROP TRIGGER IF EXISTS trg_orders_au;

DELIMITER $$

-- When an order fails, release its seats: delete its tickets, then orphaned virtual STANDING seats
CREATE TRIGGER trg_orders_au
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
  IF OLD.status = 'pending' AND NEW.status = 'failed' THEN
    -- Tickets first: ticket has a foreign key to seat
    DELETE FROM ticket WHERE order_id = NEW.order_id;

    DELETE FROM seat
     WHERE seat_zone = 'STANDING'
       AND NOT EXISTS (SELECT 1 FROM ticket t WHERE t.seat_id = seat.seat_id);
  END IF;
END$$

DELIMITER ;
