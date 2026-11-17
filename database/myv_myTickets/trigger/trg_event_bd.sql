DROP TRIGGER IF EXISTS trg_event_bd;

DELIMITER $$

-- Guard for deleting an event, whatever way the DELETE comes in:
--   * an event that still has tickets (pending or paid) cannot be deleted
--     (cancelling an order removes its tickets, so cancelled orders do not count)
--   * an event that has already started cannot be deleted (it is history)
CREATE TRIGGER trg_event_bd
BEFORE DELETE ON event
FOR EACH ROW
BEGIN
  IF EXISTS (SELECT 1 FROM ticket WHERE event_id = OLD.event_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event has tickets and cannot be deleted';
  END IF;
  IF OLD.start_time <= NOW() THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event has already started and cannot be deleted';
  END IF;
END$$

DELIMITER ;
