# Week 2 — Part 3: From a source file to a queryable table

[Week overview](README.md) · [Previous: PostgreSQL and pgAdmin](part-2-postgres-and-pgadmin.md) · [Runnable example](../../examples/nyc-taxi/README.md)

## Goal and working directory

First, we will understand a downloaded taxi file. Later steps define a PostgreSQL table and load it with Python.

**Step 1 runs locally with Python.** It needs no Docker, Compose configuration, database, or `.env`. Complete [the advance preparation](../../preparation/week-02.md) first: install the Parquet reader and download the data file.

The later Docker ingestion image now builds successfully. Full database-loading validation remains pending; Step 1 uses a separate local inspection script.

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

`if_exists="append"` inserts rows into the table, and `index=False` avoids adding pandas' row index as a column. The script clears the old rows first, so running the complete script again replaces the teaching dataset.

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

Repeat the SQL count. It should still show 10,000 rows, not 20,000. The script clears `taxi_trips` before inserting the selected records again. It does not change the Part 2 `connection_check` table or the downloaded file.

The clear and insert operations share one **transaction** through `with engine.begin()`: they are confirmed together on success, or undone if a database write fails. The simplified script has no failure-simulation or full-month command-line options.

**Checkpoint:** Explain why a successful rerun does not double the number of rows.

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

### 5. Explain a failure

The delete and all inserts for **one month** form one transaction. A write failure restores that month's earlier rows. Previously completed months remain committed. The job stops on the error; fix it and rerun the affected month rather than downloading and loading every month again.

A database lock lasts for the month's load and prevents simultaneous jobs from changing the table at the same time. For this exercise, run one loader at a time and close unfinished pgAdmin transactions.

**Finish with:** two complete source months in PostgreSQL, matching row counts, and an explanation of why the batch loop must append while the month replacement happens once outside that loop.

**Discuss:** Why do we label rows with their source-file month instead of deleting rows based on their pickup timestamps? What would you need to consider if TLC published a corrected version of a file already saved in `data/`?

## Troubleshooting and completion

- **Old code runs:** rebuild with `docker compose build ingest` after editing Python or SQL files.
- **File not found:** check the filename and make sure the downloaded file is in `examples/nyc-taxi/data`. The loader does not download it.
- **Connection fails:** revisit Part 2's service status and credentials. Changing `.env` does not reset an existing database password.
- **Required source field/type changed:** inspect the source again and decide on a deliberate schema update. The loader will not silently invent columns or migrate existing SQL tables.
- **`TypeError` during loading:** inspect nullable integer fields for fractional or incompatible values. Earlier successful data is retained.
- **Queries or loads wait:** ensure pgAdmin does not hold an unfinished transaction; the loader uses a 10-second lock timeout.
- **Step 7 reports an HTTP error:** confirm that TLC has published the requested yellow taxi file. The job stops at that month; earlier successful months remain loaded.
- **Step 7 reuses an outdated local file:** replace that month's prepared file with the intended version, or move it out of `data/` to let the script download it again. Existing local files are reused without checking whether TLC has revised them.

Keep your source observations, count results, and rerun evidence. For your project, explain whether replacing the entire dataset would be acceptable as its volume grows. Incremental loading and scheduling follow in later weeks.

## References

- [TLC trip-record data and dictionaries](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [PyArrow Parquet reader](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
- [pandas database writes](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html)
- [SQLAlchemy connections and transactions](https://docs.sqlalchemy.org/en/20/core/connections.html)
- [Compose profiles](https://docs.docker.com/compose/how-tos/profiles/)
