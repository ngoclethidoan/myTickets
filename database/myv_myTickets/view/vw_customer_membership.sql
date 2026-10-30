-- Membership of every customer: total paid, current rank and discount, and the next rank (if any).
--   spent          sum of ticket_price over tickets of PAID orders (cancelled and pending orders do not count)
--   next_tier      NULL when the customer is already at the top rank
--   next_min_spent total needed for the next rank
-- Used by pc_book_tickets (discount) and by the web app (badge and progress).
--
-- Usage:
--   SELECT * FROM vw_customer_membership WHERE customer_id = 'CU0001';
CREATE OR REPLACE VIEW vw_customer_membership AS
SELECT
  s.customer_id,
  s.spent,
  t.tier_name,
  t.discount_percent,
  n.tier_name AS next_tier,
  n.min_spent AS next_min_spent
FROM (
  SELECT c.customer_id,
         COALESCE((SELECT SUM(tk.ticket_price)
                     FROM ticket tk
                     JOIN orders o ON o.order_id = tk.order_id
                    WHERE tk.customer_id = c.customer_id
                      AND o.status = 'paid'), 0) AS spent
    FROM customer c
) s
JOIN      membership_tier t ON t.min_spent = (SELECT MAX(m.min_spent) FROM membership_tier m WHERE m.min_spent <= s.spent)
LEFT JOIN membership_tier n ON n.min_spent = (SELECT MIN(m.min_spent) FROM membership_tier m WHERE m.min_spent >  s.spent);
