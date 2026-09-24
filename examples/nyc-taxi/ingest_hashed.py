"""Load selected taxi months, skipping records whose hash already exists."""

import argparse
from datetime import date
import hashlib
import json
import os
from numbers import Integral
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pyarrow.parquet as pq
from sqlalchemy import URL, create_engine, text
from sqlalchemy.dialects.postgresql import insert

from ingest_months import download_month


# These fields define what this exercise considers the same trip record.
HASH_COLUMNS = [
    "vendor_id", "pickup_time", "dropoff_time", "pickup_zone_id",
    "dropoff_zone_id", "fare_amount_usd", "trip_distance_miles",
]


def row_hash(values):
    # JSON preserves field boundaries and distinguishes missing values from text.
    values = [None if pd.isna(value) else
              value.isoformat() if isinstance(value, pd.Timestamp) else
              int(value) if isinstance(value, Integral) else value
              for value in values]
    encoded = json.dumps(values, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def insert_new_rows(table, connection, keys, data_iter):
    """pandas calls this function for each group of up to 1,000 rows."""
    rows = [dict(zip(keys, row)) for row in data_iter]
    statement = insert(table.table).values(rows)
    statement = statement.on_conflict_do_nothing(index_elements=["row_hash"])
    statement = statement.returning(table.table.c.row_hash)
    return len(connection.execute(statement).fetchall())


def load_month(file_path, year, month, engine):
    columns = {
        "VendorID": "vendor_id",
        "tpep_pickup_datetime": "pickup_time",
        "tpep_dropoff_datetime": "dropoff_time",
        "passenger_count": "passenger_count",
        "trip_distance": "trip_distance_miles",
        "PULocationID": "pickup_zone_id",
        "DOLocationID": "dropoff_zone_id",
        "fare_amount": "fare_amount_usd",
        "total_amount": "total_amount_usd",
    }
    source_month = date(year, month, 1)
    schema = (Path(__file__).parent / "sql/schema-hashed.sql").read_text()
    with pq.ParquetFile(file_path) as source:
        expected = source.metadata.num_rows
        if expected == 0 or not set(columns).issubset(source.schema_arrow.names):
            raise ValueError("The source is empty or lacks required yellow taxi columns.")

        # Commit all new rows for this file together; roll back on failure.
        with engine.begin() as connection:
            # Limit waiting for locks, not the total ingestion time.
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text(schema))
            processed = inserted = 0
            for batch in source.iter_batches(batch_size=10_000, columns=list(columns)):
                trips = batch.to_pandas().rename(columns=columns)
                for name in ("vendor_id", "passenger_count", "pickup_zone_id", "dropoff_zone_id"):
                    trips[name] = trips[name].astype("Int64")
                # Normalize measure types so 10 and 10.0 produce the same key.
                for name in ("fare_amount_usd", "trip_distance_miles"):
                    trips[name] = trips[name].astype("float64")
                trips["row_hash"] = [row_hash(row) for row in
                    trips[HASH_COLUMNS].itertuples(index=False, name=None)]
                trips["source_month"] = source_month
                inserted += trips.to_sql(
                    "taxi_trips_hashed", connection, schema="public",
                    if_exists="append", index=False, chunksize=1_000,
                    method=insert_new_rows,
                )
                processed += len(trips)
                print(f"{source_month:%Y-%m}: read {processed:,}/{expected:,} rows (not committed yet)")
            if processed != expected:
                raise ValueError("Not all source rows were processed; rolling back.")
    print(f"Committed {source_month:%Y-%m}: read {processed:,}, inserted {inserted:,}, "
          f"skipped {processed - inserted:,}")
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Publication year, e.g. 2024")
    parser.add_argument("--months", type=int, choices=range(1, 13), nargs="+", required=True,
                        help="Months to load, e.g. 1 2 3")
    args = parser.parse_args()
    if not 2009 <= args.year <= date.today().year:
        parser.error("Choose a year from 2009 through the current year.")

    url = URL.create(
        "postgresql+psycopg", host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=5432, database=os.environ["POSTGRES_DB"],
        username=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
    )
    engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
    try:
        # Check credentials before downloading potentially large files.
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        for month in sorted(set(args.months)):
            with TemporaryDirectory() as directory:
                path = download_month(args.year, month, directory)
                load_month(path, args.year, month, engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
