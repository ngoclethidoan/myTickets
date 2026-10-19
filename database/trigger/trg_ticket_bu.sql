DROP TRIGGER IF EXISTS trg_ticket_bu;

DELIMITER $$

-- Tickets of a paid order are locked; seat_id and event_id are the key and cannot change
CREATE TRIGGER trg_ticket_bu
BEFORE UPDATE ON ticket
FOR EACH ROW
BEGIN
  IF (SELECT status FROM orders WHERE order_id = OLD.order_id) = 'paid' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ticket is already paid and cannot be modified';
  END IF;
  IF NEW.seat_id <> OLD.seat_id OR NEW.event_id <> OLD.event_id THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The seat or event of a ticket cannot be changed';
  END IF;
END$$

DELIMITER ;
