"""Check multi-month loading in a disposable database ending in _test."""

from collections import Counter
from datetime import date, datetime
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError

from ingest_months import download_month, load_month


class MonthlyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("POSTGRES_DB", "").endswith("_test"):
            raise RuntimeError("Use a disposable database ending in _test")
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
        # Includes NULLs and a pickup timestamp outside the declared source month.
        self.table = pa.table({
            "VendorID": [1, 2],
            "tpep_pickup_datetime": [datetime(2024, 1, 1), datetime(2023, 12, 31)],
            "tpep_dropoff_datetime": [datetime(2024, 1, 1, 1)] * 2,
            "passenger_count": [1.0, None], "trip_distance": [2.5, -1.0],
            "PULocationID": [161, 237], "DOLocationID": [237, 161],
            "fare_amount": [10.0, -5.0], "total_amount": [12.0, -6.0],
        })
        pq.write_table(self.table, self.path)
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS public.taxi_trips_monthly"))

    def snapshot(self):
        with self.engine.connect() as connection:
            return Counter(connection.execute(text("SELECT * FROM taxi_trips_monthly")).fetchall())

    def test_all_batches_two_months_and_rerun(self):
        large = pa.concat_tables([self.table] * 5001)  # 10,002 rows, including a partial last batch.
        pq.write_table(large, self.path)
        self.assertEqual(load_month(self.path, 2024, 1, self.engine), 10002)
        pq.write_table(self.table, self.path)
        load_month(self.path, 2024, 2, self.engine)
        before = self.snapshot()
        load_month(self.path, 2024, 2, self.engine)
        self.assertEqual(before, self.snapshot())
        with self.engine.connect() as connection:
            counts = dict(connection.execute(text(
                "SELECT source_month, COUNT(*) FROM taxi_trips_monthly GROUP BY source_month"
            )).fetchall())
        self.assertEqual(counts, {date(2024, 1, 1): 10002, date(2024, 2, 1): 2})

    def test_failure_in_second_batch_preserves_both_months(self):
        load_month(self.path, 2024, 1, self.engine)
        load_month(self.path, 2024, 2, self.engine)
        before = self.snapshot()
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE taxi_trips_monthly ADD CHECK (vendor_id < 10)"))
        large = pa.concat_tables([self.table] * 5001)
        large = large.set_column(0, "VendorID", pa.array([1] * 10000 + [99, 99]))
        pq.write_table(large, self.path)
        with self.assertRaises(IntegrityError):
            load_month(self.path, 2024, 1, self.engine)
        self.assertEqual(before, self.snapshot())

    def test_empty_source_preserves_month(self):
        load_month(self.path, 2024, 1, self.engine)
        before = self.snapshot()
        pq.write_table(self.table.slice(0, 0), self.path)
        with self.assertRaises(ValueError):
            load_month(self.path, 2024, 1, self.engine)
        self.assertEqual(before, self.snapshot())

    def test_download_url_and_prepared_file_reuse(self):
        contents = self.path.read_bytes()
        with patch("ingest_months.Path.is_file", return_value=False), patch(
            "ingest_months.urlopen", return_value=io.BytesIO(contents)
        ) as request:
            downloaded = download_month(2024, 2, self.directory.name)
            self.assertEqual(downloaded.read_bytes(), contents)
            self.assertIn("yellow_tripdata_2024-02.parquet", request.call_args.args[0])
        with patch("ingest_months.Path.is_file", return_value=True), patch("ingest_months.urlopen") as request:
            self.assertEqual(download_month(2024, 2, self.directory.name), Path("data/yellow_tripdata_2024-02.parquet"))
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
