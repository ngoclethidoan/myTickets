USE myv_myTickets_admin;

DROP PROCEDURE IF EXISTS pc_delete_event;

DELIMITER $$

-- Delete an event of the MAIN database and write it to audit_log. Only a super_admin may do this.
--   p_admin_id  the admin who performs the action (must exist and be a super_admin)
--   p_event_id  the event to delete
-- The business rules (no tickets, not started yet) are enforced by the trigger trg_event_bd
-- in the main database, so they also hold for any other DELETE on event.
-- Delete and audit_log row are saved together or not at all (transaction).
CREATE PROCEDURE pc_delete_event(
  IN p_admin_id VARCHAR(20),
  IN p_event_id VARCHAR(20)
)
BEGIN
  DECLARE v_level VARCHAR(20);

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
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only a super admin can delete events';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM myv_myTickets.event WHERE event_id = p_event_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Event not found';
  END IF;

  START TRANSACTION;

  DELETE FROM myv_myTickets.event WHERE event_id = p_event_id;

  INSERT INTO audit_log (admin_id, action, target_id)
  VALUES (p_admin_id, 'DELETE_EVENT', p_event_id);

  COMMIT;
END$$

DELIMITER ;
