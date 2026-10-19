DROP FUNCTION IF EXISTS fn_available_seats;

DELIMITER $$

-- Count the real seats of an event's venue that have no ticket yet (paid or pending) for this event.
-- Virtual STANDING seats are not counted.
-- p_seat_zone = NULL counts every zone; otherwise only the given zone.
-- Returns NULL when the event does not exist.
--
-- Usage:
--   SELECT fn_available_seats('EV01', NULL);
--   SELECT fn_available_seats('EV01', 'VIP');
--   SELECT event_id, event_name, fn_available_seats(event_id, NULL) AS seats_left FROM event;
CREATE FUNCTION fn_available_seats(
  p_event_id  VARCHAR(20),
  p_seat_zone VARCHAR(20)
)
RETURNS INT
READS SQL DATA
BEGIN
  DECLARE v_venue_id VARCHAR(20);
  DECLARE v_cnt      INT;

  SELECT venue_id INTO v_venue_id FROM event WHERE event_id = p_event_id;
  IF v_venue_id IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT COUNT(*) INTO v_cnt
    FROM seat s
   WHERE s.venue_id  = v_venue_id
     AND s.seat_zone <> 'STANDING'
     AND (p_seat_zone IS NULL OR s.seat_zone = p_seat_zone)
     AND NOT EXISTS (SELECT 1 FROM ticket t
                      WHERE t.seat_id  = s.seat_id
                        AND t.event_id = p_event_id);

  RETURN v_cnt;
END$$

DELIMITER ;
