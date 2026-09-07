"""Integration checks; run only against a disposable database ending in _test."""

import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError

from ingest import load_trips


class PipelineChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Use a disposable POSTGRES_DB ending in _test")
        cls.engine = create_engine(URL.create(
            "postgresql+psycopg", host=os.environ.get("POSTGRES_HOST", "postgres"),
            database=os.environ["POSTGRES_DB"], username=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
        ))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.parquet"
        self.table = pa.table({
            "VendorID": [1, 1, 2],
            "tpep_pickup_datetime": [datetime(2024, 1, 1, 9)] * 3,
            "tpep_dropoff_datetime": [datetime(2024, 1, 1, 10)] * 3,
            "passenger_count": [1.0, None, 2.0],
            "trip_distance": [2.5, 2.5, -1.0],
            "PULocationID": [161, 161, 237],
            "DOLocationID": [237, 237, 161],
            "fare_amount": [10.0, 10.0, -5.0],
            "total_amount": [12.0, 12.0, -6.0],
        })
        pq.write_table(self.table, self.path)
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS taxi_trips"))
            connection.execute(text((Path(__file__).parents[1] / "sql/schema.sql").read_text()))
        load_trips(self.path, self.engine)

    def snapshot(self):
        with self.engine.connect() as connection:
            trips = connection.execute(text("""
                SELECT * FROM taxi_trips
                ORDER BY vendor_id, passenger_count NULLS LAST, total_amount_usd
            """)).fetchall()
            return trips

    def test_rerun_preserves_rows_and_nulls(self):
        before = self.snapshot()
        load_trips(self.path, self.engine)
        after = self.snapshot()
        self.assertEqual(before, after)
        self.assertEqual(len(after), 3)
        self.assertIsNone(after[1].passenger_count)
        self.assertEqual(after[2].total_amount_usd, -6)

    def test_database_failure_restores_old_rows(self):
        before = self.snapshot()
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE taxi_trips ADD CHECK (vendor_id < 10)"))
        invalid = self.table.set_column(0, "VendorID", pa.array([1, 1, 99]))
        pq.write_table(invalid, self.path)
        with self.assertRaises(IntegrityError):
            load_trips(self.path, self.engine)
        self.assertEqual(before, self.snapshot())

    def test_empty_file_preserves_existing_rows(self):
        before = self.snapshot()
        pq.write_table(self.table.slice(0, 0), self.path)
        with self.assertRaises(ValueError):
            load_trips(self.path, self.engine)
        self.assertEqual(before, self.snapshot())

    def test_limit_is_ten_thousand(self):
        pq.write_table(pa.concat_tables([self.table] * 4000), self.path)
        load_trips(self.path, self.engine)
        self.assertEqual(len(self.snapshot()), 10_000)


if __name__ == "__main__":
    unittest.main()
