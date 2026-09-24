"""Run against a disposable PostgreSQL database ending in _test."""
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import IntegrityError

from ingest_hashed import load_month


class HashLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('POSTGRES_DB', '').endswith('_test'):
            raise RuntimeError('Use a disposable database ending in _test')
        cls.engine = create_engine(URL.create(
            'postgresql+psycopg', host=os.environ.get('POSTGRES_HOST', 'postgres'),
            database=os.environ['POSTGRES_DB'], username=os.environ['POSTGRES_USER'],
            password=os.environ['POSTGRES_PASSWORD']))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def test_duplicates_reruns_changes_and_rollback(self):
        with self.engine.begin() as c:
            c.execute(text('DROP TABLE IF EXISTS public.taxi_trips_hashed'))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'input.parquet'

            def write(fares, passengers=None):
                n = len(fares)
                pq.write_table(pa.table({
                    'VendorID': [1]*n,
                    'tpep_pickup_datetime': [datetime(2024, 1, 1, 9)]*n,
                    'tpep_dropoff_datetime': [datetime(2024, 1, 1, 10)]*n,
                    'passenger_count': passengers or [None]*n,
                    'trip_distance': [2.5]*n,
                    'PULocationID': [161]*n, 'DOLocationID': [None]*n,
                    'fare_amount': fares, 'total_amount': [12.0]*n,
                }), path)

            # The same key appears within batches and across the 10,000-row boundary.
            write([10.0]*10_001)
            self.assertEqual(load_month(path, 2024, 1, self.engine), 1)
            self.assertEqual(load_month(path, 2024, 1, self.engine), 0)
            write([10.0, 11.0], [2, 2])
            self.assertEqual(load_month(path, 2024, 2, self.engine), 1)
            with self.engine.begin() as c:
                self.assertEqual(c.scalar(text('SELECT count(*) FROM taxi_trips_hashed')), 2)
                self.assertEqual(c.scalar(text('SELECT count(*) FROM taxi_trips_hashed WHERE passenger_count IS NULL')), 1)
                c.execute(text('ALTER TABLE taxi_trips_hashed ADD CHECK (fare_amount_usd < 50)'))
            # Fail after an earlier batch inserted a new key: that insert must roll back.
            write([12.0]*10_000 + [99.0])
            with self.assertRaises(IntegrityError):
                load_month(path, 2024, 3, self.engine)
            with self.engine.connect() as c:
                self.assertEqual(c.scalar(text('SELECT count(*) FROM taxi_trips_hashed')), 2)


if __name__ == '__main__':
    unittest.main()
