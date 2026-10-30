-- membership_tier: loyalty ranks. A customer's rank is NOT stored; it is computed from how much
-- they have paid (see vw_customer_membership), so it can never get out of date.
--   min_spent         total of paid tickets needed to reach this rank (VND)
--   discount_percent  % taken off the list price when booking
-- There must always be one rank with min_spent = 0, otherwise new customers would have no rank.
CREATE TABLE IF NOT EXISTS membership_tier (
  tier_name        VARCHAR(20)   NOT NULL,
  min_spent        DECIMAL(12,2) NOT NULL,
  discount_percent TINYINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (tier_name),
  CONSTRAINT uq_tier_min_spent UNIQUE (min_spent),
  CONSTRAINT chk_tier_min_spent CHECK (min_spent >= 0),
  CONSTRAINT chk_tier_discount  CHECK (discount_percent BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Starting ranks (INSERT IGNORE: running this script again never duplicates or overwrites them)
INSERT IGNORE INTO membership_tier (tier_name, min_spent, discount_percent) VALUES
  ('Bronze',        0,  0),
  ('Silver',  3000000,  5),
  ('Gold',   10000000, 10),
  ('Platinum', 25000000, 15);
