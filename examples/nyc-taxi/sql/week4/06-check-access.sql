-- Execute ONE numbered block at a time, with Auto commit enabled.

-- 1. Inspect the mapping as the administrator first.
SELECT * FROM week4_private.customers ORDER BY email;

-- 2. Switch permissions in this Query Tool connection.
SET ROLE deng_week4_analyst;
SELECT current_user;

-- 3. This works: two tokens, booking counts 2 and 1, totals 30.00 and 25.00.
SELECT customer_token, COUNT(*) AS bookings, SUM(amount_usd) AS total_usd
FROM week4_shared.bookings
GROUP BY customer_token;

-- 4. This must fail: permission denied for schema week4_private.
SELECT * FROM week4_private.customers;

-- 5. Run separately after the expected error to restore administrator access.
RESET ROLE;
SELECT current_user;
