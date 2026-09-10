"""Load the prepared TLC taxi-zone CSV for the Week 3 SQL exercise."""

import argparse
import csv
import os
from pathlib import Path

from sqlalchemy import URL, create_engine, text


def load_zones(file_path, engine):
    with open(file_path, newline="", encoding="utf-8-sig") as source:
        zones = [dict(location_id=int(row["LocationID"]), borough=row["Borough"],
                      zone=row["Zone"], service_zone=row["service_zone"])
                 for row in csv.DictReader(source)]
    if not zones:
        raise ValueError("The zone file is empty.")
    schema = Path(__file__).parent / "sql/week3/01-zones.sql"
    with engine.begin() as connection:
        connection.execute(text(schema.read_text()))
        connection.execute(text("DELETE FROM public.taxi_zones"))
        connection.execute(text("""
            INSERT INTO public.taxi_zones VALUES
            (:location_id, :borough, :zone, :service_zone)
        """), zones)
    print(f"Loaded {len(zones)} taxi zones. Existing trip records were kept.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Path to taxi_zone_lookup.csv")
    args = parser.parse_args()
    url = URL.create("postgresql+psycopg", host=os.environ.get("POSTGRES_HOST", "postgres"),
                     port=5432, database=os.environ["POSTGRES_DB"],
                     username=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"])
    engine = create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)
    try:
        load_zones(args.file, engine)
    finally:
        engine.dispose()
