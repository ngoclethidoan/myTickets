DROP TRIGGER IF EXISTS trg_event_bu_chk;

DELIMITER $$

-- Same validation as trg_event_bi_chk, applied on update
CREATE TRIGGER trg_event_bu_chk
BEFORE UPDATE ON event
FOR EACH ROW
BEGIN
  IF NEW.sale_time >= NEW.start_time THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'sale_time must be earlier than start_time';
  END IF;
  IF NEW.standing_capacity < 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'standing_capacity cannot be negative';
  END IF;
END$$

DELIMITER ;
