DROP TRIGGER IF EXISTS trg_ticket_bd;

DELIMITER $$

-- Tickets of a paid order cannot be deleted
CREATE TRIGGER trg_ticket_bd
BEFORE DELETE ON ticket
FOR EACH ROW
BEGIN
  IF (SELECT status FROM orders WHERE order_id = OLD.order_id) = 'paid' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ticket is already paid and cannot be cancelled';
  END IF;
END$$

DELIMITER ;
