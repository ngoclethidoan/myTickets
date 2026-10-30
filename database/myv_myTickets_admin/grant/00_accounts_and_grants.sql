-- ==========================================================
-- 01_accounts_and_grants.sql : two MySQL accounts, each with the minimum rights it needs
--
-- Run this LAST, after both databases are fully built (tables, view, function, procedures),
-- because GRANT only works on objects that already exist.
-- Run it as your admin account (avnadmin), not as one of the two new accounts.
--
-- BEFORE running: replace both CHANGE_ME passwords with your own strong passwords
-- and keep them somewhere safe (they go into the Python app's settings later).
--
-- The procedures, triggers and view run with the rights of whoever CREATED them (your admin account),
-- so these accounts do not need rights on the tables behind them. That is why the lists below are short.
-- ==========================================================

-- ----------------------------------------------------------
-- customer_app : used by the app when a CUSTOMER is logged in. Sees the main database only.
-- ----------------------------------------------------------
CREATE USER IF NOT EXISTS 'customer_app'@'%' IDENTIFIED BY 'CHANGE_ME_customer_password';

-- Sign up and sign in
GRANT SELECT, INSERT ON myv_myTickets.customer TO 'customer_app'@'%';
-- Browse events
GRANT SELECT ON myv_myTickets.event TO 'customer_app'@'%';
GRANT SELECT ON myv_myTickets.venue TO 'customer_app'@'%';
-- Order history
GRANT SELECT ON myv_myTickets.vw_order_history TO 'customer_app'@'%';
-- Membership rank and discount (the app filters by the logged-in customer, like the order history)
GRANT SELECT ON myv_myTickets.vw_customer_membership TO 'customer_app'@'%';
GRANT SELECT ON myv_myTickets.membership_tier        TO 'customer_app'@'%';
-- Book, pay, cancel and check free seats: only through these routines
GRANT EXECUTE ON PROCEDURE myv_myTickets.pc_book_tickets    TO 'customer_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets.pc_pay_order       TO 'customer_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets.pc_cancel_order    TO 'customer_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets.pc_available_seats TO 'customer_app'@'%';
GRANT EXECUTE ON FUNCTION  myv_myTickets.fn_available_seats TO 'customer_app'@'%';

-- ----------------------------------------------------------
-- admin_app : used by the app when an ADMIN is logged in. Sees the admin database plus a few reads on the main one.
-- ----------------------------------------------------------
CREATE USER IF NOT EXISTS 'admin_app'@'%' IDENTIFIED BY 'CHANGE_ME_admin_password';

-- Sign in and read the audit log
GRANT SELECT ON myv_myTickets_admin.admin     TO 'admin_app'@'%';
GRANT SELECT ON myv_myTickets_admin.audit_log TO 'admin_app'@'%';
-- Add events and read stats: only through these procedures
GRANT EXECUTE ON PROCEDURE myv_myTickets_admin.pc_add_event   TO 'admin_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets_admin.pc_event_stats TO 'admin_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets_admin.pc_delete_event TO 'admin_app'@'%';
-- Read-only access to the main database, for the dashboard forms and the free-seat list
GRANT SELECT ON myv_myTickets.event TO 'admin_app'@'%';
GRANT SELECT ON myv_myTickets.venue TO 'admin_app'@'%';
GRANT EXECUTE ON PROCEDURE myv_myTickets.pc_available_seats TO 'admin_app'@'%';
GRANT EXECUTE ON FUNCTION  myv_myTickets.fn_available_seats TO 'admin_app'@'%';

-- ----------------------------------------------------------
-- Check what each account can do (run these one at a time):
-- SHOW GRANTS FOR 'customer_app'@'%';
-- SHOW GRANTS FOR 'admin_app'@'%';
-- ----------------------------------------------------------
