DROP TRIGGER IF EXISTS trg_seat_bi;

DELIMITER $$

-- Generate seat_id = 'SE' + running number (SE0001, SE0002, ...) for real seats.
-- Skipped when seat_id is already given, e.g. the virtual STND-... seats inserted by trg_ticket_bi.
CREATE TRIGGER trg_seat_bi
BEFORE INSERT ON seat
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF NEW.seat_id IS NULL OR NEW.seat_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(seat_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM seat
     WHERE seat_id REGEXP '^SE[0-9]+$';

    SET NEW.seat_id = CONCAT('SE', LPAD(v_next, GREATEST(4, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
