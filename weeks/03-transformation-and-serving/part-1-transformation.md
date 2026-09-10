# Week 3 — Part 1: From taxi records to a daily report

[Week 3 overview](README.md) · [Next: tokenization](part-2-tokenization.md)

## Goal and starting point

Create a report of trip counts and fare totals per pickup date and zone using the records already in `public.taxi_trips_monthly`. We will preserve those records and create SQL views that derive fields, flag records, and calculate totals.

Use the Week 2 database `ny_taxi` in pgAdmin. Open its Query Tool, as in [Week 2 Part 2](../02-postgresql-and-ingestion/part-2-postgres-and-pgadmin.md). Run:

```sql
SELECT COUNT(*) AS input_rows FROM public.taxi_trips_monthly;
```

Record the count. If the table is missing or empty, complete [Week 2 Part 3, Step 7](../02-postgresql-and-ingestion/part-3-python-ingestion.md#step-7--download-and-load-several-complete-months). One complete month is sufficient for this exercise; you can also use all 12 months of 2024. The monthly loader replaces each requested month on rerun.

Wait for ingestion to finish before comparing counts: each month's rows become visible only after that month commits. Run this query to see which source months are available:

```sql
SELECT source_month, COUNT(*) AS loaded_rows
FROM public.taxi_trips_monthly
GROUP BY source_month
ORDER BY source_month;
```

The views use all committed records in this table. Full-year queries can take longer than sample queries. Our report describes the loaded yellow taxi files under the rules below; it does not cover every taxi service or every component of revenue.

If you already created Week 3's views using the small table or the `week3` schema, rerun `03-transform.sql`, then `04-report.sql` below. The updated files create the views in `public` using the monthly table. Query these `public` views from now on; any earlier views in `week3` remain separate.

All terminal commands below run from `examples/nyc-taxi`. If the services are stopped:

```sh
docker compose up -d --wait
```

## Step 1 — Inspect before deciding what to change

Open [02-inspect.sql](../../examples/nyc-taxi/sql/week3/02-inspect.sql) in your editor. Copy each query into pgAdmin and execute it separately. `WHERE` keeps rows meeting a condition; `IS NULL` finds missing values.

Record the number of missing passenger counts, negative fares, and drop-offs before pickups. Read a few matching records. A count of zero is a valid result; your loaded data may not contain every issue.

**Discuss:** Is a missing passenger count the same as zero passengers? Could a negative fare represent an adjustment? What additional information would help you decide?

**Finish with:** your input count and three quality counts. No records have been changed.

## Step 2 — Load the zone names

The trip table contains numeric zone identifiers. A **lookup table** maps each identifier to a name and borough. You have already downloaded `taxi_zone_lookup.csv` into `examples/nyc-taxi/data/` as part of the [Week 3 preparation](../../preparation/week-03.md). This file supplies that mapping.

Run:

```sh
docker compose run --rm ingest load_zones.py data/taxi_zone_lookup.csv
```

Here `ingest` selects our existing Python container environment; `load_zones.py` selects the script. This script reads the local CSV, creates `public.taxi_zones`, and loads the mapping. It does not download anything. Rerunning replaces only this lookup table's rows in one transaction; it keeps the trip records.

If Python says the script does not exist, rebuild the image with `docker compose build ingest`.

In pgAdmin, run:

```sql
SELECT * FROM public.taxi_zones ORDER BY location_id LIMIT 10;
```

`public` is the same **schema** (a namespace for database objects) that contains our monthly trips table. `location_id` is the lookup table's primary key: there can be only one mapping per identifier. Refresh the Schemas entry in pgAdmin if you want to browse the new objects.

**Finish with:** a lookup table you can query and an explanation of why two names for the same identifier would cause trouble during a join.

## Step 3 — Derive fields, enrich, and flag records

Read [03-transform.sql](../../examples/nyc-taxi/sql/week3/03-transform.sql). Before executing it, use this guide:

| SQL expression | What it does here |
|---|---|
| `CREATE OR REPLACE VIEW` | Saves a query under a name; rerunning updates its definition. |
| `t` and `z` | Short aliases for the trip and zone tables. For example, `t.pickup_time` selects the trip table's pickup time. |
| `CAST(pickup_time AS DATE)` | Returns the date part of the pickup timestamp. |
| `EXTRACT(EPOCH FROM (...)) / 60.0` | Converts the difference between timestamps into minutes. |
| `LEFT JOIN ... ON ...` | Looks up the pickup-zone identifier; keeps the trip even if no mapping exists. |
| `CASE ... WHEN ... ELSE ... END` | Assigns a reporting status using the first matching condition. |

Our teaching report applies these rules in the listed order:

| Condition | Status | Treatment in report |
|---|---|---|
| Missing pickup time, drop-off time, or fare | `missing_required_value` | Exclude from this report; retain for inspection. |
| Drop-off is at or before pickup | `nonpositive_duration` | Exclude from this report; retain for inspection. |
| Fare is negative | `negative_fare` | Exclude from this report; investigate separately. |
| Pickup identifier has no lookup row | `unmatched_pickup_zone` | Exclude from this report; investigate the mapping. |
| None of the above | `included` | Include in this report. |

Missing passenger counts remain `NULL` and do not exclude a trip: this report does not require passenger counts. A lookup entry labelled unknown is still a matched entry; matching is not proof of a precise location. These are explicit exercise rules, not a complete definition of a trustworthy trip.

Copy and execute the SQL file in pgAdmin. Then inspect the view:

```sql
SELECT pickup_time, pickup_date, duration_minutes,
       pickup_zone_name, passenger_count, report_status
FROM public.trips_reviewed
LIMIT 20;
```

Compare its count with your original input count:

```sql
SELECT COUNT(*) AS reviewed_rows FROM public.trips_reviewed;
```

The counts must match. The left join retains unmatched trips, and the unique lookup key prevents a trip from matching several lookup rows.

**Discuss:** Why might an inner join hide a data-quality problem? If one record has two issues, why does our status show only one? The separate inspection queries can count overlapping issues; `CASE` gives each record one status.

**Finish with:** a queryable view with dates, durations, zone names, and reporting statuses. The original table is unchanged.

## Step 4 — Build a report for a consumer

Our consumer is an analyst exploring historical trips in the loaded dataset. The requested output is one row per **pickup date and pickup zone**, containing a trip count and the sum of included fare amounts.

Read [04-report.sql](../../examples/nyc-taxi/sql/week3/04-report.sql):

- `WHERE report_status = 'included'` applies our reporting rules.
- `GROUP BY` gathers records with the same date and zone.
- `COUNT(*)` counts records in each group; `SUM` adds their fares.
- `CAST(... AS NUMERIC)` performs the aggregation using decimal arithmetic; it cannot recover precision already lost in the stored values.
- `ROUND(..., 2)` presents the total with two decimal places.
- `AS` labels a result column, such as `fare_total_usd`.

Run the file's statements individually. The last two queries must return the same count: every included record belongs to exactly one report group. `COALESCE(..., 0)` shows zero if the report is empty instead of a missing sum.

The metric is **the sum of nonnegative fare amounts for records meeting our rules**. It is not total revenue, profit, or the total charged including all extras. Its date comes from pickup time, not from the source-file month.

**Finish with:** a daily report, matching included/reported counts, and a sentence explaining what the total measures and what it leaves out.

## Step 5 — Change a rule and explain its effect

Predict what happens if negative fares are included. In `03-transform.sql`, remove the `WHEN t.fare_amount_usd < 0 ...` line from the view definition and execute the changed definition. Query the report again.

The existing report view uses the updated reviewed view immediately; you do not need to reload the taxi file. Counts and totals may change, depending on the data and the other rules. Restore the original definition afterward.

**Discuss:** Would this revised metric answer the same business question? Why does retaining input records make this comparison possible? Could running the report daily make monthly published data fresh enough for a live congestion alert?

## If something fails

- **Missing `public.taxi_zones`:** complete Step 2 before creating the views.
- **Missing local CSV:** check `examples/nyc-taxi/data/taxi_zone_lookup.csv` and complete the preparation checklist.
- **Unexpected totals:** check the loaded source months, reporting rules, and whether ingestion is still running. Rerun the view definitions if they previously used the small table.
- **No report rows:** count the statuses in `public.trips_reviewed`; inspect the excluded records and the lookup table.
- **Values look different from a partner's:** compare input counts and loaded files before comparing transformations.

Continue to [Part 2 — Tokenization and access](part-2-tokenization.md).
