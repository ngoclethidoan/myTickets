USE myv_myTickets_admin;

DROP PROCEDURE IF EXISTS pc_update_event;

DELIMITER $$

-- Edit an event of the MAIN database and write it to audit_log. Only a super_admin may do this.
--   p_admin_id          the admin who performs the action (must exist and be a super_admin)
--   p_event_id          the event to edit
--   p_standing_capacity 0 (or NULL) means the event has no standing area
-- What can change: name, artist, sale time, start time and standing capacity.
-- What cannot change: the venue (the seats of sold tickets belong to it) and the event_id.
-- Rules:
--   * an event that has already started is history and cannot be edited
--   * standing capacity cannot go below the standing tickets that already exist (paid or pending)
--   * sale_time < start_time and capacity >= 0 come from trg_event_bu_chk in the main database
-- Event and audit_log row are saved together or not at all (transaction).
CREATE PROCEDURE pc_update_event(
  IN p_admin_id          VARCHAR(20),
  IN p_event_id          VARCHAR(20),
  IN p_event_name        VARCHAR(150),
  IN p_artist            VARCHAR(150),
  IN p_sale_time         DATETIME,
  IN p_start_time        DATETIME,
  IN p_standing_capacity INT
)
BEGIN
  DECLARE v_level    VARCHAR(20);
  DECLARE v_start    DATETIME;
  DECLARE v_standing INT;

  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SELECT `level` INTO v_level FROM admin WHERE admin_id = p_admin_id;
  IF v_level IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Admin not found';
  END IF;
  IF v_level <> 'super_admin' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only a super admin can edit events';
  END IF;

  IF p_event_name IS NULL OR TRIM(p_event_name) = '' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event name is required';
  END IF;
  IF p_sale_time IS NULL OR p_start_time IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Sale time and start time are required';
  END IF;

  START TRANSACTION;

  -- Lock the event row while we check it
  SELECT start_time INTO v_start
    FROM myv_myTickets.event WHERE event_id = p_event_id FOR UPDATE;
  IF v_start IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event not found';
  END IF;
  IF v_start <= NOW() THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event has already started and cannot be edited';
  END IF;

  SELECT COUNT(*) INTO v_standing
    FROM myv_myTickets.ticket t
    JOIN myv_myTickets.seat s ON s.seat_id = t.seat_id
   WHERE t.event_id = p_event_id AND s.seat_zone = 'STANDING';
  IF COALESCE(p_standing_capacity, 0) < v_standing THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Standing capacity cannot be lower than the standing tickets already booked';
  END IF;

  UPDATE myv_myTickets.event
     SET event_name        = TRIM(p_event_name),
         artist            = NULLIF(TRIM(COALESCE(p_artist, '')), ''),
         sale_time         = p_sale_time,
         start_time        = p_start_time,
         standing_capacity = COALESCE(p_standing_capacity, 0)
   WHERE event_id = p_event_id;

  INSERT INTO audit_log (admin_id, action, target_id)
  VALUES (p_admin_id, 'UPDATE_EVENT', p_event_id);

  COMMIT;
END$$

DELIMITER ;
