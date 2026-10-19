DROP TRIGGER IF EXISTS trg_event_bi_id;

DELIMITER $$

-- Generate event_id = 'EV' + running number (EV01, EV02, ... EV100) when none is given
CREATE TRIGGER trg_event_bi_id
BEFORE INSERT ON event
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF NEW.event_id IS NULL OR NEW.event_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(event_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM event
     WHERE event_id REGEXP '^EV[0-9]+$';

    SET NEW.event_id = CONCAT('EV', LPAD(v_next, GREATEST(2, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
