DROP PROCEDURE IF EXISTS pc_add_event;

DELIMITER $$

-- Create a new event at an existing venue and return its generated event_id.
-- trg_event_bi_id generates the id; trg_event_bi_chk validates sale_time < start_time
-- and standing_capacity >= 0. p_standing_capacity = 0 (or NULL) means no standing area.
CREATE PROCEDURE pc_add_event(
  IN  p_venue_id          VARCHAR(20),
  IN  p_event_name        VARCHAR(150),
  IN  p_artist            VARCHAR(150),
  IN  p_sale_time         DATETIME,
  IN  p_start_time        DATETIME,
  IN  p_standing_capacity INT,
  OUT p_event_id          VARCHAR(20)
)
BEGIN
  SET p_event_id = NULL;

  IF NOT EXISTS (SELECT 1 FROM venue WHERE venue_id = p_venue_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue not found';
  END IF;

  INSERT INTO event (event_id, venue_id, event_name, artist, sale_time, start_time, standing_capacity)
  VALUES (NULL, p_venue_id, p_event_name, p_artist, p_sale_time, p_start_time,
          COALESCE(p_standing_capacity, 0));

  -- Read back the generated id: the newest matching event
  SELECT event_id INTO p_event_id
    FROM event
   WHERE venue_id   = p_venue_id
     AND event_name = p_event_name
     AND start_time = p_start_time
   ORDER BY CAST(SUBSTRING(event_id, 3) AS UNSIGNED) DESC
   LIMIT 1;
END$$

DELIMITER ;
