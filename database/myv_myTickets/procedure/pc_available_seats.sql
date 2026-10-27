DROP PROCEDURE IF EXISTS pc_available_seats;

DELIMITER $$

-- List the real seats of an event's venue that have no ticket yet for this event.
-- Virtual STANDING seats are not listed.
-- p_seat_zone = NULL lists every zone; otherwise only the given zone.
-- Read-only: changes nothing.
CREATE PROCEDURE pc_available_seats(
  IN p_event_id  VARCHAR(20),
  IN p_seat_zone VARCHAR(20)
)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM event WHERE event_id = p_event_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event not found';
  END IF;

  SELECT s.seat_id, s.seat_zone, s.seat_row, s.seat_number
    FROM seat s
    JOIN event e ON e.venue_id = s.venue_id
   WHERE e.event_id  = p_event_id
     AND s.seat_zone <> 'STANDING'
     AND (p_seat_zone IS NULL OR s.seat_zone = p_seat_zone)
     AND NOT EXISTS (SELECT 1 FROM ticket t
                      WHERE t.seat_id  = s.seat_id
                        AND t.event_id = e.event_id)
   ORDER BY s.seat_zone, s.seat_row, s.seat_number;
END$$

DELIMITER ;
