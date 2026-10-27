DROP TRIGGER IF EXISTS trg_venue_bi;

DELIMITER $$

-- Generate venue_id = 'VE' + running number (VE01, VE02, ... VE100) when none is given
CREATE TRIGGER trg_venue_bi
BEFORE INSERT ON venue
FOR EACH ROW
BEGIN
  DECLARE v_next INT;

  IF NEW.venue_id IS NULL OR NEW.venue_id = '' THEN
    SELECT COALESCE(MAX(CAST(SUBSTRING(venue_id, 3) AS UNSIGNED)), 0) + 1
      INTO v_next
      FROM venue
     WHERE venue_id REGEXP '^VE[0-9]+$';

    -- LPAD truncates when the number is longer than the width, so the width never drops below the length
    SET NEW.venue_id = CONCAT('VE', LPAD(v_next, GREATEST(2, CHAR_LENGTH(v_next)), '0'));
  END IF;
END$$

DELIMITER ;
