-- Step 2: one row represents one record from the selected source file.
-- Business fields are nullable: preserve missing values for investigation.
CREATE TABLE IF NOT EXISTS public.taxi_trips (
    vendor_id INTEGER,
    pickup_time TIMESTAMP WITHOUT TIME ZONE,
    dropoff_time TIMESTAMP WITHOUT TIME ZONE,
    passenger_count INTEGER,
    trip_distance_miles DOUBLE PRECISION,
    pickup_zone_id INTEGER,
    dropoff_zone_id INTEGER,
    fare_amount_usd DOUBLE PRECISION,
    total_amount_usd DOUBLE PRECISION
);
