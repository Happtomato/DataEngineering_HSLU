# Week 2 — Part 3: From a source file to a queryable table

[Week overview](README.md) · [Previous: PostgreSQL and pgAdmin](part-2-postgres-and-pgadmin.md) · [Runnable example](../../examples/nyc-taxi/README.md)

## Goal and working directory

First, we will understand a downloaded taxi file. Later steps define a PostgreSQL table and load it with Python.

**Step 1 runs locally with Python.** It needs no Docker, Compose configuration, database, or `.env`. Complete [the advance preparation](../../preparation/week-02.md) first: install the Parquet reader and download the data file.

Later steps run the Python ingestion scripts in Docker to load taxi records into PostgreSQL.

## Step 1 — Open the file and understand its records

**Goal:** describe what the taxi dataset contains before loading anything into a database.

### 1. Open a terminal in the example directory

From the repository root:

```sh
cd examples/nyc-taxi
```

Your downloaded file should be at `data/yellow_tripdata_2024-01.parquet`. Keep it there after the exercise so it can be opened again without another download.

### 2. Run the inspection script

On macOS/Linux, using the Python environment prepared before class:

```sh
.venv/bin/python inspect_source.py data/yellow_tripdata_2024-01.parquet
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe inspect_source.py data/yellow_tripdata_2024-01.parquet
```

The first part chooses the prepared Python interpreter. `inspect_source.py` is the script to run. The final argument tells it **which file to open**. This path is relative to your current directory, `examples/nyc-taxi`. If your file is elsewhere, pass its actual path; put paths containing spaces in quotes.

The script prints:

- the number of rows;
- column names and data types;
- the first five records, with each field's name and value.

It reads the local file and leaves it unchanged. It does not download, delete, or load anything into PostgreSQL. Running it again uses the same file. There is no need to open `source.py` for this step; that file belongs to the later ingestion code.

**Parquet** is the file format. **PyArrow** is the Python library that opens it. A Parquet file is binary, so a text editor will not display it as a readable table.

### 3. Look up the fields and discuss

Open the [official TLC data dictionary](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) for yellow taxi trips and discuss with your partner:

1. What does one row represent, and how many rows does the file contain?
2. What do pickup time, trip distance, pickup zone ID, and total amount mean?
3. Which field would help us count trips by day?
4. What missing or unexpected values could affect the analysis? Five records cannot show every quality issue in the file.

**Finish with:** a short description of the dataset and the fields you would use to count trips by day. That is the end of Step 1. No table has been created in PostgreSQL.

If you downloaded green taxi data instead, the script can inspect that file too; use its filename and the green taxi dictionary. The later loader currently expects the yellow taxi schema, so the two files are not interchangeable there.

## Step 2 — Create an empty destination table

**Goal:** turn the source fields you explored in Step 1 into a table structure in PostgreSQL. We will create the destination now; Python will load records into it later.

### 1. Read and discuss the table definition

Open [sql/schema.sql](../../examples/nyc-taxi/sql/schema.sql). Focus on the first statement, `CREATE TABLE IF NOT EXISTS public.taxi_trips (...)`. 

Match the source columns to the destination columns below. Discuss why pickup time needs a timestamp, passenger count needs a whole number, and trip distance needs a number that can contain a fractional part.

| Source field | Destination field | SQL type and reason |
|---|---|---|
| `VendorID` | `vendor_id` | `INTEGER`: an identifier, not a measurement. |
| `tpep_pickup_datetime`, `tpep_dropoff_datetime` | `pickup_time`, `dropoff_time` | `TIMESTAMP WITHOUT TIME ZONE`: preserves the source's timezone-naive values; we do not label them as UTC. |
| `passenger_count` | `passenger_count` | Nullable `INTEGER`: a whole-number count may be missing. |
| `trip_distance` | `trip_distance_miles` | `DOUBLE PRECISION`: retains a source measurement. |
| `PULocationID`, `DOLocationID` | `pickup_zone_id`, `dropoff_zone_id` | Nullable `INTEGER`: identifiers for taxi zones. |
| `fare_amount`, `total_amount` | `fare_amount_usd`, `total_amount_usd` | `DOUBLE PRECISION`: preserves the source's floating-point amounts for inspection. Accounting calculations would require a deliberate decimal and rounding policy. |

**Grain:** One row represents one source trip record from the selected file. Two identical-looking source records remain two rows; we do not invent a deduplication rule.

Business fields accept `NULL`, meaning a missing value. Suspicious negative amounts and distances are retained for investigation. Successful ingestion does not mean the source data is clean.

### 2. Create the table in pgAdmin

1. Start PostgreSQL and pgAdmin as described in [Part 2](part-2-postgres-and-pgadmin.md), if they are not already running.
2. In pgAdmin, select the `ny_taxi` database and open **Tools → Query Tool**.
3. Enable **Auto commit?** in the dropdown beside **Execute script**, so the table creation is committed automatically.
4. Copy only the first `CREATE TABLE` statement from `schema.sql`, through its closing `);`, into the Query Tool and execute it.

`CREATE TABLE` defines the columns and their types. `public` is the schema namespace containing the table. `IF NOT EXISTS` allows the statement to be run again without recreating an existing table; it does not change an existing table's structure or remove its data.

### 3. Verify the empty table

Run:

```sql
SELECT * FROM public.taxi_trips;
```

On your first run, the result should show the defined column headings and **zero rows**. This is expected: creating a table does not copy records from the Parquet file.

Confirm the count separately:

```sql
SELECT COUNT(*) AS row_count FROM public.taxi_trips;
```

The count query returns one result row containing `0`. That result row reports the count; it is not a taxi record.

Refresh **Schemas → public → Tables** in pgAdmin and find `taxi_trips`. Expand its columns to inspect their types. 
### What you have achieved

You now have an **empty destination table whose columns and types you can explain** (or an existing table retained from an earlier run). The source file remains unchanged, and this step has not loaded any trip records.

Step 3 explains the Python code that will prepare and write records; Step 4 runs it. The loader expects the table you created in Step 2 to exist.

**Checkpoint:** Show your table and row count to your partner. Explain one source-to-destination column mapping, one type choice, and why a missing passenger count should not automatically become zero.

## Step 3 — Follow the Python loading code

Read [ingest.py](../../examples/nyc-taxi/ingest.py) from top to bottom. `load_trips()` reads a small subset from the local file, renames its columns, and writes the rows into PostgreSQL. The block at the bottom reads the file-path argument and configures the database connection using environment variables.

The Python libraries each have a role:

- **PyArrow:** reads Parquet metadata and batches.
- **pandas:** represents each batch as a DataFrame—a table of rows and columns in Python memory.
- **SQLAlchemy:** manages the PostgreSQL connection and transaction and supports pandas' database writes.
- **psycopg:** the driver that communicates with PostgreSQL underneath SQLAlchemy.

There are two different batch sizes:

- `batch_size=10_000` with `next(...)` reads only the first group of up to **10,000 records** from the file. It does not iterate through the remaining groups.
- `chunksize=1_000` in `trips.to_sql(...)` sends those selected records to PostgreSQL in groups of **1,000**. It does not reduce the total to 1,000.

`if_exists="append"` adds rows to the existing table, and `index=False` avoids adding pandas' row index as a column. The `TRUNCATE` line is commented out with `#`, so it does not run. Existing rows stay in the table, and each run adds the same first 10,000 records again.

**Checkpoint:** Find where the script selects records, renames columns, and writes to PostgreSQL. Explain the difference between the two batch sizes.

## Step 4 — Run ingestion through Compose

Complete Part 2 and create the table in Step 2 first. Use your existing `.env`. This loader runs in Docker and reads the file you downloaded for Step 1. Compose makes your local `data` folder available at `/app/data` inside the container, read-only. Keep the file at `examples/nyc-taxi/data/yellow_tripdata_2024-01.parquet`.

Build the ingestion image (or reuse the image built before class):

```sh
docker compose build ingest
```

This prepares Python, its libraries, and the loader code inside an image; it does not execute ingestion. Rebuild after editing the loader code.

If you stopped PostgreSQL and pgAdmin after Part 2, start them again:

```sh
docker compose up -d --wait
```

The `ingest` service uses a Compose **profile** named `tools`, so this ordinary startup runs PostgreSQL and pgAdmin only. Explicitly naming `ingest` in `docker compose run` starts the one-off Python service and its required database dependency.

Load the first 10,000 records:

```sh
docker compose run --rm ingest ingest.py data/yellow_tripdata_2024-01.parquet
```

The file path is the only argument. The script already limits the read to 10,000 records; no `--limit` option is supported. For this file, successful completion prints `Loaded 10,000 rows into taxi_trips.`

Python connects to host `postgres`, port `5432`, using the database credentials supplied by Compose. It does not connect through pgAdmin. On completion the Python container exits; PostgreSQL and pgAdmin remain available.



## Step 5 — Verify the data through pgAdmin

Refresh the tables under `ny_taxi → Schemas → public → Tables`. Open a Query Tool for `ny_taxi` and run the statements in [sql/verification.sql](../../examples/nyc-taxi/sql/verification.sql) separately.

Check these outcomes:

1. `SELECT COUNT(*) FROM public.taxi_trips;` returns 10,000, matching the number printed by Python.
2. A preview of ten rows has understandable fields. SQL does not guarantee the original file order.
3. Quality queries report missing values, reversed timestamps, and negative values. Investigate their meaning before deciding whether to reject them.
4. The daily query describes only the loaded records. This first-10,000 subset is not a representative sample and does not measure all January taxi demand.

**Checkpoint:** Explain the difference between successfully copying records and deciding that their values are suitable for analysis.

## Step 6 — Run the loader again

Run the same command again:

```sh
docker compose run --rm ingest ingest.py data/yellow_tripdata_2024-01.parquet
```

Repeat the SQL count. If you started with an empty table, the first successful run loaded 10,000 rows and this second run brings the total to 20,000. Each successful run adds another 10,000 rows from the same file. If you have already run the script more times, your total will be higher.

These are repeated copies of the same first 10,000 records, not the next 10,000 records in the file. The script starts reading from the beginning each time and does not check whether those records are already in the table.

All inserts for one run share one **transaction** through `with engine.begin()`: they are confirmed together on success, or undone if a database write fails. Rows from earlier successful runs remain in place.

**Checkpoint:** Explain why the second run increases the count to 20,000 even though the source file has not changed. Does this mean you have loaded 20,000 different trips?

## Step 7 — Download and load several complete months

**Goal:** extend the first-batch example to all records, then repeat the process for several monthly files. Use [ingest_months.py](../../examples/nyc-taxi/ingest_months.py), a separate script that leaves the earlier `taxi_trips` exercise alone.

Allow about 20 minutes for reading and discussion, plus loading time. Each complete month contains millions of records; start with one month, and add a second while you discuss the design. Loading can take several minutes or longer depending on your laptop.

### 1. Follow the two loops

Open the script and find:

- The **month loop** in `main()`: obtain a file and load it for each requested month.
- The **batch loop** in `load_month()`: read every batch from that file, not just the first batch.

```python
for batch in source.iter_batches(batch_size=10_000, columns=list(columns)):
    # Prepare and append this batch.
```

Each batch contains up to 10,000 records. The final batch can be smaller. `chunksize=1000` still controls the smaller groups written to PostgreSQL; it does not limit how many records we read overall.

`download_month()` constructs the official TLC URL from the year and month. For example, year `2024` and month `2` select `yellow_tripdata_2024-02.parquet`. If that exact filename is already in your prepared `data/` folder, the script reuses it. Otherwise it downloads it automatically to temporary storage for that month's run. Newly downloaded temporary files are deleted after the month finishes; files in `data/` are kept.

### 2. Understand where the rows go

The script creates a separate table, `public.taxi_trips_monthly`, using [schema-monthly.sql](../../examples/nyc-taxi/sql/schema-monthly.sql). It contains the same trip fields plus **`source_month`**, which records the month of the source file.

For example, all records from the January 2024 file receive `2024-01-01`. We use the first day as a simple way to store a month in a SQL `DATE` column. This is the file's month, not a claim about the actual pickup date: some source records can have timestamps outside that month.

Before loading January, the script deletes only previously loaded January rows from this table. February and other months stay in place. There is no full-table `TRUNCATE` in this script.

**Predict:** What would happen to January's data if we cleared the entire table before loading February? What would happen if we deleted January inside every batch iteration?

### 3. Choose a year and months, then run

From `examples/nyc-taxi`, rebuild the image to include the new script (preferably before class):

```sh
docker compose build ingest
```

Ensure the `data/` directory exists, even if you want automatic downloads, because the Compose service mounts it. Start with January:

```sh
docker compose run --rm ingest ingest_months.py --year 2024 --months 1
```

Then add February:

```sh
docker compose run --rm ingest ingest_months.py --year 2024 --months 2
```

To request both in one run:

```sh
docker compose run --rm ingest ingest_months.py --year 2024 --months 1 2
```

`--year` selects one year. `--months` accepts a space-separated list of month numbers from 1 to 12. To load every available file for a complete year, list `1 2 3 4 5 6 7 8 9 10 11 12`. There is no need to request a whole year for this exercise. Files must have been published by TLC; a valid month number does not guarantee an available file.

Watch the progress: records written should keep increasing beyond 10,000. The final `Committed` message reports the month's complete count. The script checks that the database count for that month matches the file's row count before confirming the load.

### 4. Verify and rerun

In pgAdmin's Query Tool for `ny_taxi`, run:

```sql
SELECT source_month, COUNT(*) AS loaded_rows
FROM public.taxi_trips_monthly
GROUP BY source_month
ORDER BY source_month;
```

After both loads, expect two result rows, one per source month. Compare their counts with the script's final messages.

Run January again and repeat the query. January's count should remain the same for the same file; February should still be present with its earlier count. This replaces a month's records on rerun rather than duplicating them. It does not attempt to identify and remove duplicate records already present in the source.


## Step 8 — Use a hash to skip records already loaded

**Goal:** compare Step 7's monthly replacement with inserting only records whose key is new. Use [ingest_hashed.py](../../examples/nyc-taxi/ingest_hashed.py). It writes to a new table, `public.taxi_trips_hashed`, leaving the earlier tables and their views unchanged.

### 1. Understand the record key

A **hash** is a fingerprint calculated from values. The same input values produce the same hash. Our script uses SHA-256 on these seven fields:

- vendor ID;
- pickup and drop-off timestamps;
- pickup and drop-off zone IDs;
- fare amount;
- trip distance.

Read `HASH_COLUMNS` and `row_hash()` in the script. Before hashing, the script normalizes numeric types and encodes the values as a JSON list. This preserves field boundaries and missing values: we do not simply join values into an ambiguous string.

This is our chosen definition of an identical record, **not an official unique trip ID**. Different trips with identical selected values will be treated as one record. Passenger count and total amount are not part of this key: changes to them alone will be skipped. A changed fare produces a new hash and therefore a new row. This exercise does not synchronize corrections or deletions from a revised source file.

### 2. Follow the insertion

The script reuses Step 7's download function and reads every batch. It adds `row_hash` to each record, then inserts it into the new table.

The [table definition](../../examples/nyc-taxi/sql/schema-hashed.sql) declares `row_hash` as a **primary key**. PostgreSQL enforces uniqueness. The insertion uses `ON CONFLICT (row_hash) DO NOTHING`: if the key already exists, skip that record. This also handles repeated keys within the input and across batches.

Unlike Step 7, this script does not delete destination rows. Each monthly file still uses one transaction: all its new rows commit together, or roll back on failure. Earlier months already committed remain saved.

`source_month` records the file that first inserted the key. It is not included in the hash, so an identical key in another month's file is also skipped.

### 3. Build, run and verify

From `examples/nyc-taxi`, with PostgreSQL running and the `data/` directory present:

```sh
docker compose build ingest
docker compose run --rm ingest ingest_hashed.py --year 2024 --months 1
```

The script reuses the prepared January file, or downloads it temporarily, just as in Step 7. To request several months, use `--months 1 2`.

The final message reports how many records were **read**, **inserted**, and **skipped**. On the first run, some source records may already share the same key, so the inserted count can be smaller than the file's row count.

In pgAdmin, run:

```sql
SELECT COUNT(*) AS stored_rows,
       COUNT(DISTINCT row_hash) AS distinct_keys
FROM public.taxi_trips_hashed;
```

The two counts must match. Note the count, rerun the same January command, then run the query again. For an unchanged file, the second run should insert **zero** rows and leave the count unchanged. It still reads and hashes the file; it does not skip downloading or processing merely because the month was loaded before.

### 4. Compare the approaches

| Question | Step 7: monthly replacement | Step 8: hash-based insertion |
|---|---|---|
| What happens on a rerun? | Delete and reload the selected month. | Keep existing rows; insert only new keys. |
| Repeated records inside a file? | Preserve every source row. | Keep one row per hash. |
| A fare is corrected? | Replace the month's old version. | Insert a new key; the old row remains. |
| A row disappears from the source? | Remove it when replacing that month. | Keep the old row. |

**Discuss:** Why must the hash stay the same on a rerun? Why would a randomly generated UUID not achieve this?

**Discuss:** Which columns would you choose to identify a trip, and what could go wrong with that choice?

**Checkpoint:** Explain why a successful hash-based load does not require the destination count to equal the source file's row count.

## References

- [TLC trip-record data and dictionaries](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [PyArrow Parquet reader](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
- [pandas database writes](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html)
- [SQLAlchemy connections and transactions](https://docs.sqlalchemy.org/en/20/core/connections.html)
- [Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)

The code and explanations were written independently for DENG.
