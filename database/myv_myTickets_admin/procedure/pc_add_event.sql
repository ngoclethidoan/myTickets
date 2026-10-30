USE myv_myTickets_admin;

DROP PROCEDURE IF EXISTS pc_add_event;

DELIMITER $$

-- Create a new event in the MAIN database and write it to audit_log. Only a super_admin may do this.
--   p_admin_id          the admin who performs the action (must exist and be a super_admin)
--   p_standing_capacity 0 (or NULL) means the event has no standing area
--   p_event_id (OUT)    the generated event_id, for example EV07
-- The event ids and the rules (sale_time < start_time, capacity >= 0) come from the triggers
-- trg_event_bi_id and trg_event_bi_chk in the main database.
-- Event and audit_log row are saved together or not at all (transaction).
CREATE PROCEDURE pc_add_event(
  IN  p_admin_id          VARCHAR(20),
  IN  p_venue_id          VARCHAR(20),
  IN  p_event_name        VARCHAR(150),
  IN  p_artist            VARCHAR(150),
  IN  p_sale_time         DATETIME,
  IN  p_start_time        DATETIME,
  IN  p_standing_capacity INT,
  OUT p_event_id          VARCHAR(20)
)
BEGIN
  DECLARE v_level VARCHAR(20);

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SET p_event_id = NULL;

  SELECT `level` INTO v_level FROM admin WHERE admin_id = p_admin_id;
  IF v_level IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Admin not found';
  END IF;
  IF v_level <> 'super_admin' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only a super admin can add events';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM myv_myTickets.venue WHERE venue_id = p_venue_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Venue not found';
  END IF;

  START TRANSACTION;

  INSERT INTO myv_myTickets.event
         (event_id, venue_id, event_name, artist, sale_time, start_time, standing_capacity)
  VALUES (NULL, p_venue_id, p_event_name, p_artist, p_sale_time, p_start_time,
          COALESCE(p_standing_capacity, 0));

  -- Read back the generated id: the newest matching event
  SELECT event_id INTO p_event_id
    FROM myv_myTickets.event
   WHERE venue_id   = p_venue_id
     AND event_name = p_event_name
     AND start_time = p_start_time
   ORDER BY CAST(SUBSTRING(event_id, 3) AS UNSIGNED) DESC
   LIMIT 1;

  INSERT INTO audit_log (admin_id, action, target_id)
  VALUES (p_admin_id, 'ADD_EVENT', p_event_id);

  COMMIT;
END$$

DELIMITER ;
