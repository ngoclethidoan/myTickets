-- Order history: one row per ticket, together with its order, customer, event, venue and seat.
-- LEFT JOINs keep orders that currently have no tickets (for example failed or cancelled orders,
-- whose tickets were released by trg_orders_au), so they still show up in the history.
--
-- Usage:
--   SELECT * FROM vw_order_history WHERE customer_id = 'CU0001';
--   SELECT * FROM vw_order_history WHERE order_status = 'paid';
CREATE OR REPLACE VIEW vw_order_history AS
SELECT
  o.order_id,
  o.place_at,
  o.status      AS order_status,
  o.customer_id,
  c.username,
  c.name        AS customer_name,
  t.event_id,
  e.event_name,
  e.artist,
  e.start_time,
  v.venue_id,
  v.address     AS venue_address,
  t.seat_id,
  s.seat_zone,
  s.seat_row,
  s.seat_number,
  t.ticket_price,
  t.is_standing,
  t.pay_method,
  t.pay_date
FROM orders o
JOIN      customer c ON c.customer_id = o.customer_id
LEFT JOIN ticket   t ON t.order_id    = o.order_id
LEFT JOIN event    e ON e.event_id    = t.event_id
LEFT JOIN venue    v ON v.venue_id    = e.venue_id
LEFT JOIN seat     s ON s.seat_id     = t.seat_id;
