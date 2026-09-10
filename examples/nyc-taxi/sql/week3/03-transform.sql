-- A view saves this query. It does not modify the source records.
CREATE OR REPLACE VIEW public.trips_reviewed AS
SELECT
    t.vendor_id, t.pickup_time, t.dropoff_time, t.passenger_count,
    t.trip_distance_miles, t.pickup_zone_id, t.dropoff_zone_id,
    t.fare_amount_usd, t.total_amount_usd,
    CAST(t.pickup_time AS DATE) AS pickup_date,
    EXTRACT(EPOCH FROM (t.dropoff_time - t.pickup_time)) / 60.0 AS duration_minutes,
    z.zone AS pickup_zone_name,
    z.borough AS pickup_borough,
    CASE
        WHEN t.pickup_time IS NULL OR t.dropoff_time IS NULL
             OR t.fare_amount_usd IS NULL THEN 'missing_required_value'
        WHEN t.dropoff_time <= t.pickup_time THEN 'nonpositive_duration'
        WHEN t.fare_amount_usd < 0 THEN 'negative_fare'
        WHEN z.location_id IS NULL THEN 'unmatched_pickup_zone'
        ELSE 'included'
    END AS report_status,
    t.source_month
FROM public.taxi_trips_monthly AS t
LEFT JOIN public.taxi_zones AS z ON t.pickup_zone_id = z.location_id;

SELECT report_status, COUNT(*) AS records
FROM public.trips_reviewed
GROUP BY report_status
ORDER BY report_status;
