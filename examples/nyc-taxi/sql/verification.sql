-- Step 5: run these separately in pgAdmin's Query Tool, connected to ny_taxi.
-- Compare this with the row count printed by Python (up to 10,000).
SELECT COUNT(*) AS loaded_rows FROM public.taxi_trips;

-- A preview of ten rows; SQL does not guarantee file order.
SELECT * FROM public.taxi_trips LIMIT 10;

-- Quality observations, not automatic deletion rules.
SELECT COUNT(*) AS rows,
       COUNT(*) FILTER (WHERE pickup_time IS NULL) AS missing_pickup,
       COUNT(*) FILTER (WHERE passenger_count IS NULL) AS missing_passenger_count,
       COUNT(*) FILTER (WHERE dropoff_time < pickup_time) AS reversed_times,
       COUNT(*) FILTER (WHERE trip_distance_miles < 0) AS negative_distance,
       COUNT(*) FILTER (WHERE total_amount_usd < 0) AS negative_total,
       MIN(pickup_time) AS earliest_pickup,
       MAX(pickup_time) AS latest_pickup
FROM public.taxi_trips;

-- Describes only the loaded data. A first-N sample cannot estimate monthly demand.
SELECT CAST(pickup_time AS DATE) AS pickup_date,
       COUNT(*) AS recorded_trips,
       AVG(trip_distance_miles) AS average_distance_miles
FROM public.taxi_trips
GROUP BY CAST(pickup_time AS DATE)
ORDER BY pickup_date;
