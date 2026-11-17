DROP FUNCTION IF EXISTS fn_standing_left;

DELIMITER $$

-- How many STANDING tickets of an event can still be sold:
-- standing_capacity minus the standing tickets that already exist (paid or pending).
-- The counterpart of fn_available_seats, which only counts numbered seats.
-- Returns 0 when the event has no standing area, NULL when the event does not exist.
--
-- Usage:
--   SELECT fn_standing_left('EV01');
--   SELECT event_id, event_name, fn_standing_left(event_id) AS standing_left FROM event;
CREATE FUNCTION fn_standing_left(
  p_event_id VARCHAR(20)
)
RETURNS INT
READS SQL DATA
BEGIN
  DECLARE v_capacity INT;
  DECLARE v_used     INT;

  SELECT standing_capacity INTO v_capacity FROM event WHERE event_id = p_event_id;
  IF v_capacity IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT COUNT(*) INTO v_used
    FROM ticket t
    JOIN seat s ON s.seat_id = t.seat_id
   WHERE t.event_id  = p_event_id
     AND s.seat_zone = 'STANDING';

  RETURN GREATEST(v_capacity - v_used, 0);
END$$

DELIMITER ;
