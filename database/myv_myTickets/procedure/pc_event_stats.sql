DROP PROCEDURE IF EXISTS pc_event_stats;

DELIMITER $$

-- One-row report for an event:
--   tickets_paid     tickets of paid orders
--   tickets_pending  tickets of pending orders (held, not paid yet)
--   revenue          sum of ticket_price over paid tickets only
--   seats_left       real seats without any ticket (paid or pending)
--   standing_left    standing_capacity minus standing tickets (paid or pending)
-- Read-only: changes nothing.
CREATE PROCEDURE pc_event_stats(
  IN p_event_id VARCHAR(20)
)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM event WHERE event_id = p_event_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event not found';
  END IF;

  SELECT
    e.event_id,
    e.event_name,
    e.artist,
    (SELECT COUNT(*)
       FROM ticket t
       JOIN orders o ON o.order_id = t.order_id
      WHERE t.event_id = e.event_id AND o.status = 'paid')    AS tickets_paid,
    (SELECT COUNT(*)
       FROM ticket t
       JOIN orders o ON o.order_id = t.order_id
      WHERE t.event_id = e.event_id AND o.status = 'pending') AS tickets_pending,
    (SELECT COALESCE(SUM(t.ticket_price), 0)
       FROM ticket t
       JOIN orders o ON o.order_id = t.order_id
      WHERE t.event_id = e.event_id AND o.status = 'paid')    AS revenue,
    (SELECT COUNT(*)
       FROM seat s
      WHERE s.venue_id = e.venue_id AND s.seat_zone <> 'STANDING')
    - (SELECT COUNT(*)
         FROM ticket t
         JOIN seat s ON s.seat_id = t.seat_id
        WHERE t.event_id = e.event_id AND s.seat_zone <> 'STANDING') AS seats_left,
    e.standing_capacity
    - (SELECT COUNT(*)
         FROM ticket t
         JOIN seat s ON s.seat_id = t.seat_id
        WHERE t.event_id = e.event_id AND s.seat_zone = 'STANDING')  AS standing_left
  FROM event e
  WHERE e.event_id = p_event_id;
END$$

DELIMITER ;
