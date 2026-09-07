"""Load the first 10,000 records from a local yellow taxi file into PostgreSQL."""

import argparse
import os

import pyarrow.parquet as pq
from sqlalchemy import URL, create_engine, text


def load_trips(file_path, engine):
    # 1. Open the downloaded file and read a small subset.
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
    with pq.ParquetFile(file_path) as source:
        batch = next(source.iter_batches(batch_size=10_000, columns=list(columns)), None)
    if batch is None:
        raise ValueError("The file is empty; existing database rows were not changed.")

    # 2. Rename the selected columns; keep missing integer values as NULL.
    trips = batch.to_pandas().rename(columns=columns)
    for name in ("vendor_id", "passenger_count", "pickup_zone_id", "dropoff_zone_id"):
        trips[name] = trips[name].astype("Int64")

    # 3. Connect. Step 2 must have created taxi_trips already.
    # 4. Replace its rows and insert our subset in one transaction.
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        connection.execute(text("TRUNCATE TABLE public.taxi_trips"))
        trips.to_sql("taxi_trips", connection, schema="public",
                     if_exists="append", index=False, chunksize=1_000)
    print(f"Loaded {len(trips):,} rows into taxi_trips.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Path to the downloaded yellow taxi Parquet file")
    args = parser.parse_args()
    url = URL.create(
        "postgresql+psycopg", host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=5432, database=os.environ["POSTGRES_DB"],
        username=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
    )
    engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
    try:
        load_trips(args.file, engine)
    finally:
        engine.dispose()
