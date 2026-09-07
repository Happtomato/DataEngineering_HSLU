# Week 2 — Part 3: From a source file to a queryable table

[Week overview](README.md) · [Previous: PostgreSQL and pgAdmin](part-2-postgres-and-pgadmin.md) · [Runnable example](../../examples/nyc-taxi/README.md)

## Goal and working directory

First, we will understand a downloaded taxi file. Later steps define a PostgreSQL table and load it with Python.

**Step 1 runs locally with Python.** It needs no Docker, Compose configuration, database, or `.env`. Complete [the advance preparation](../../preparation/week-02.md) first: install the Parquet reader and download the data file.

The later Docker ingestion implementation is still a draft with a dependency-lock issue; see [validation status](../../examples/nyc-taxi/VALIDATION.md). That issue does not affect this separate local inspection script.

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

It reads the local file and leaves it unchanged. It does not download, delete, or load anything into PostgreSQL. Running it again uses the same file. The inspection script is independent of the database loader.

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

Open [sql/schema.sql](../../examples/nyc-taxi/sql/schema.sql). It contains the statement `CREATE TABLE IF NOT EXISTS public.taxi_trips (...)`.

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
4. Copy the `CREATE TABLE` statement from `schema.sql`, through its closing `);`, into the Query Tool and execute it.

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

Refresh **Schemas → public → Tables** in pgAdmin and find `taxi_trips`. Expand its columns to inspect their types. If you have already loaded taxi data in a previous run, the table may contain rows; this creation statement leaves them intact. Do not delete existing data merely to reproduce the empty-table result.

### What you have achieved

You now have an **empty destination table whose columns and types you can explain** (or an existing table retained from an earlier run). The source file remains unchanged, and this step has not loaded any trip records.

Step 3 explains the Python code that will prepare and write records; Step 4 runs it. The loader expects this table to exist; it will not create it for you.

**Checkpoint:** Show your table and row count to your partner. Explain one source-to-destination column mapping, one type choice, and why a missing passenger count should not automatically become zero.

## Step 3 — Read the short Python loader

**Goal:** understand how Python moves records from the file into the table you created.

Open [ingest.py](../../examples/nyc-taxi/ingest.py). Follow the four numbered comments:

1. **Read:** open the saved yellow taxi file and read its first 10,000 records, or all records if there are fewer. This keeps the exercise small without reading the whole month into memory.
2. **Prepare:** select and rename the fields to match our SQL table. Keep missing integer values as missing rather than replacing them with zero.
3. **Connect:** use the PostgreSQL connection configured from environment variables.
4. **Write:** clear the teaching table's old rows and insert the selected records.

PyArrow reads Parquet. A pandas **DataFrame** holds the selected records as a table in Python memory. SQLAlchemy and its psycopg driver let Python communicate with PostgreSQL.

`trips.to_sql(...)` writes the DataFrame to our existing table. `index=False` prevents adding pandas' own row index as a database column. `chunksize=1000` sends the selected records in smaller groups.

The script takes one argument: the local file path. It does not download files, generate identifiers, record metadata, or create tables.

**Checkpoint:** Point to the column mapping and the database write. Explain which part connects the source names from Step 1 to the table names from Step 2.

## Step 4 — Run the loader

**Goal:** fill the empty table from Step 2. Complete Part 2's PostgreSQL setup and create `taxi_trips` before continuing.

The ingestion Docker image still needs its dependency-lock correction before classroom use; see [validation status](../../examples/nyc-taxi/VALIDATION.md).

From `examples/nyc-taxi`, build the Python image once that issue is resolved:

```sh
docker compose build ingest
```

Building prepares Python and its libraries. It does not load data. Rebuild after editing the script because the image contains a copy of the code.

Start the database environment, then run the loader:

```sh
docker compose up -d --wait
docker compose run --rm ingest ingest.py data/yellow_tripdata_2024-01.parquet
```

The `ingest` service is an on-demand Python environment. Compose makes your `examples/nyc-taxi/data` folder available at `/app/data` inside its container, read-only. The script runs from `/app`, so the supplied relative path finds the same downloaded file you inspected locally. The folder must exist before running the container.

Python connects to service `postgres` on port `5432`, using the database credentials from `.env`. It does not connect through pgAdmin. No dataset download takes place during ingestion.

For the chosen file, successful completion prints:

```text
Loaded 10,000 rows into taxi_trips.
```

The Python container exits afterward. Your source file remains in place, and PostgreSQL stays available for queries.

**Checkpoint:** Explain which file was read and which database table now contains its records.

## Step 5 — Inspect the loaded table

In pgAdmin, open the Query Tool for `ny_taxi` and run:

```sql
SELECT COUNT(*) FROM public.taxi_trips;
SELECT * FROM public.taxi_trips LIMIT 10;
```

Execute each statement separately. The count should match the number printed by Python: 10,000 for this file. The second query displays ten records; SQL does not guarantee the original file order.

The input file contains many more records. This is a first-10,000 subset for learning, not a random sample or the full month. Do not interpret its daily counts as total monthly taxi demand.

Use [sql/verification.sql](../../examples/nyc-taxi/sql/verification.sql) for additional missing-value checks and a simple query grouping loaded records by pickup date.

**Checkpoint:** Show a loaded row and explain why a missing passenger count remains `NULL`.

## Step 6 — Run the loader again

**Goal:** see what a rerun does. Run the same command again:

```sh
docker compose run --rm ingest ingest.py data/yellow_tripdata_2024-01.parquet
```

Repeat the SQL count. It should still be 10,000, not 20,000.

**Why:** `TRUNCATE TABLE` removes the existing rows while keeping the table definition. Python then writes the selected records again. This replaces the entire teaching dataset; it is not incremental loading.

Both actions are inside `with engine.begin()`, a **transaction**. They are confirmed together when the block finishes successfully. If a database write fails, both actions are undone, preserving the earlier rows. This basic safeguard is included even in our short script.

The loader only replaces rows in `taxi_trips`. It leaves `connection_check` and other tables alone. Close or commit unfinished pgAdmin transactions before loading; they can block the table update. The loader stops if it waits more than ten seconds for a database lock.

**Finish with:** a populated table, a count matching Python's output, and an explanation of why a rerun does not double the row count.

## Troubleshooting

- **File not found:** confirm the downloaded yellow taxi file is inside `examples/nyc-taxi/data`, with the expected name. Follow the working-directory instructions for each command.
- **Missing columns:** use yellow taxi data for this loader. Green taxi data has different timestamp field names.
- **Table does not exist:** complete Step 2 in `ny_taxi` before running the loader.
- **Old code runs:** rebuild the ingestion image after changes.
- **Database connection fails:** check Part 2's service status and credentials.
- **Load waits or times out:** commit or close unfinished Query Tool transactions.

## References

- [TLC data and dictionaries](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [PyArrow Parquet reader](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
- [pandas database writes](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html)
- [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/core/connections.html)

The code and explanations were written independently for DENG.
