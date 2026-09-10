"""Integration checks: run only in an isolated database ending in _test."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from load_zones import load_zones


SQL = Path(__file__).resolve().parents[1] / "sql"


class Week3Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = os.environ["POSTGRES_DB"]
        if not database.endswith("_test"):
            raise RuntimeError("Use a disposable database ending in _test.")
        cls.engine = create_engine(URL.create(
            "postgresql+psycopg", host=os.environ["POSTGRES_HOST"], database=database,
            username=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"]))

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with self.engine.begin() as connection:
            for schema in ("week3_private", "week3_shared"):
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            connection.execute(text("DROP VIEW IF EXISTS public.daily_zone_report"))
            connection.execute(text("DROP VIEW IF EXISTS public.trips_reviewed"))
            connection.execute(text("DROP TABLE IF EXISTS public.taxi_zones"))
            connection.execute(text("DROP TABLE IF EXISTS public.taxi_trips_monthly"))
            connection.execute(text((SQL / "schema-monthly.sql").read_text()))
            connection.execute(text((SQL / "week3/01-zones.sql").read_text()))
            connection.execute(text("INSERT INTO public.taxi_zones VALUES (1, 'Borough', 'Zone', 'Service')"))
            connection.execute(text("""
                INSERT INTO public.taxi_trips_monthly
                    (source_month, pickup_time, dropoff_time, passenger_count, pickup_zone_id, fare_amount_usd)
                VALUES
                    ('2024-01-01', '2024-01-01 10:00', '2024-01-01 10:30', NULL, 1, 12),
                    ('2024-01-01', '2024-01-01 11:00', '2024-01-01 11:15', 1, 1, 18),
                    ('2024-01-01', '2024-01-01 10:00', '2024-01-01 10:30', 1, 1, -5),
                    ('2024-01-01', '2024-01-01 10:00', '2024-01-01 09:30', 1, 1, 10),
                    ('2024-01-01', '2024-01-01 10:00', '2024-01-01 10:30', 1, 999, 10),
                    ('2024-01-01', '2024-01-01 10:00', '2024-01-01 10:30', 1, 1, NULL),
                    ('2024-01-01', NULL, '2024-01-01 10:30', 1, 1, 10)
            """))

    def run_file(self, name):
        with self.engine.begin() as connection:
            connection.execute(text((SQL / "week3" / name).read_text()))

    def test_report_counts_rules_and_rerun(self):
        self.run_file("02-inspect.sql")
        for _ in range(2):
            self.run_file("03-transform.sql")
            self.run_file("04-report.sql")
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.taxi_trips_monthly")), 7)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM public.trips_reviewed")), 7)
            statuses = dict(connection.execute(text(
                "SELECT report_status, count(*) FROM public.trips_reviewed GROUP BY report_status")).all())
            self.assertEqual(statuses, {"included": 2, "missing_required_value": 2,
                                       "nonpositive_duration": 1, "negative_fare": 1,
                                       "unmatched_pickup_zone": 1})
            row = connection.execute(text("SELECT trip_count, fare_total_usd FROM public.daily_zone_report")).one()
            self.assertEqual(tuple(row), (2, 30))
            self.assertEqual(connection.scalar(text(
                "SELECT duration_minutes FROM public.trips_reviewed WHERE passenger_count IS NULL")), 30)
        changed = (SQL / "week3/03-transform.sql").read_text().replace(
            "        WHEN t.fare_amount_usd < 0 THEN 'negative_fare'\n", "")
        with self.engine.begin() as connection:
            connection.execute(text(changed))
            row = connection.execute(text("SELECT trip_count, fare_total_usd FROM public.daily_zone_report")).one()
            self.assertEqual(tuple(row), (3, 25))

    def test_zone_reload_and_invalid_file_rollback(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "zones.csv"
            content = 'LocationID,Borough,Zone,service_zone\n1,Borough,"Zone, with comma",Service\n'
            path.write_text(content)
            load_zones(path, self.engine)
            load_zones(path, self.engine)
            path.write_text(content + '1,Other,Duplicate,Service\n')
            with self.assertRaises(IntegrityError):
                load_zones(path, self.engine)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT zone FROM public.taxi_zones")).scalar_one(),
                             "Zone, with comma")

    def test_switch_existing_views_to_monthly_table(self):
        old_view = (SQL / "week3/03-transform.sql").read_text().replace(
            "public.taxi_trips_monthly", "public.taxi_trips").replace(
            "END AS report_status,\n    t.source_month", "END AS report_status")
        with self.engine.begin() as connection:
            connection.execute(text((SQL / "schema.sql").read_text()))
            connection.execute(text(old_view))
        self.run_file("04-report.sql")
        self.run_file("03-transform.sql")
        self.run_file("04-report.sql")
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text(
                "SELECT sum(trip_count) FROM public.daily_zone_report")), 2)

    def test_token_stability_and_access_boundary(self):
        self.run_file("05-tokenization.sql")
        with self.engine.connect() as connection:
            before = connection.execute(text("SELECT * FROM week3_private.customers ORDER BY email")).all()
        self.run_file("05-tokenization.sql")
        with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            self.assertEqual(before, connection.execute(text(
                "SELECT * FROM week3_private.customers ORDER BY email")).all())
            self.assertEqual(len(before), 2)
            self.assertNotEqual(before[0].customer_token, before[1].customer_token)
            connection.execute(text("SET ROLE deng_week3_analyst"))
            try:
                self.assertEqual(connection.scalar(text("SELECT current_user")), "deng_week3_analyst")
                rows = connection.execute(text("""
                    SELECT count(*), sum(amount_usd) FROM week3_shared.bookings
                    GROUP BY customer_token ORDER BY count(*)
                """)).all()
                self.assertEqual([tuple(row) for row in rows], [(1, 25), (2, 30)])
                for table in ("customers", "bookings"):
                    with self.assertRaises(DBAPIError) as denied:
                        connection.execute(text(f"SELECT * FROM week3_private.{table}"))
                    self.assertEqual(denied.exception.orig.sqlstate, "42501")
                with self.assertRaises(DBAPIError):
                    connection.execute(text("DELETE FROM week3_shared.bookings"))
            finally:
                connection.execute(text("RESET ROLE"))


if __name__ == "__main__":
    unittest.main()
