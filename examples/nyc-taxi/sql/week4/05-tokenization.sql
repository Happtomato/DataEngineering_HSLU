-- Fictional data only. Run as the Week 2 database administrator.
BEGIN;
CREATE SCHEMA IF NOT EXISTS week4_private;
CREATE SCHEMA IF NOT EXISTS week4_shared;
REVOKE ALL ON SCHEMA week4_private FROM PUBLIC;
REVOKE ALL ON SCHEMA week4_shared FROM PUBLIC;

-- A NOLOGIN role is a permission set; it has no password or direct login.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'deng_week4_analyst') THEN
        CREATE ROLE deng_week4_analyst NOLOGIN;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS week4_private.customers (
    email TEXT PRIMARY KEY,
    customer_token UUID NOT NULL UNIQUE DEFAULT gen_random_uuid()
);
CREATE TABLE IF NOT EXISTS week4_private.bookings (
    booking_id INTEGER PRIMARY KEY,
    email TEXT NOT NULL REFERENCES week4_private.customers(email),
    amount_usd NUMERIC(10, 2) NOT NULL
);

-- On rerun, keep the earlier tokens and bookings.
INSERT INTO week4_private.customers (email) VALUES
    ('alex@example.com'), ('sam@example.com')
ON CONFLICT (email) DO NOTHING;

INSERT INTO week4_private.bookings VALUES
    (1, 'alex@example.com', 12.00),
    (2, 'alex@example.com', 18.00),
    (3, 'sam@example.com', 25.00)
ON CONFLICT (booking_id) DO NOTHING;

-- Only the token and booking fields are exposed through this view.
CREATE OR REPLACE VIEW week4_shared.bookings AS
SELECT b.booking_id, c.customer_token, b.amount_usd
FROM week4_private.bookings AS b
JOIN week4_private.customers AS c ON b.email = c.email;

REVOKE ALL ON ALL TABLES IN SCHEMA week4_private FROM PUBLIC, deng_week4_analyst;
REVOKE ALL ON SCHEMA week4_private FROM deng_week4_analyst;
GRANT USAGE ON SCHEMA week4_shared TO deng_week4_analyst;
GRANT SELECT ON week4_shared.bookings TO deng_week4_analyst;
COMMIT;
