# NYC Taxi — local database environment

Before class: [download checklist](../../preparation/week-02.md). It preloads the database images without running the exercise.

[Week 2 introduction](../../weeks/02-postgresql-and-ingestion/README.md) · [Part 2 walkthrough](../../weeks/02-postgresql-and-ingestion/part-2-postgres-and-pgadmin.md)

This example provides PostgreSQL and pgAdmin. [Part 3: Python ingestion](../../weeks/02-postgresql-and-ingestion/part-3-python-ingestion.md) and its original Python scripts are now drafted. The ingestion image build has been verified after correcting the dependency lock. Full database-loading validation remains pending.

Requirements: a running Docker engine and Docker Compose v2 with support for `up --wait`. Docker Desktop includes both. Use a terminal in this directory.

1. Copy `.env.example` to `.env` (only on first setup), and edit both passwords. The root `.gitignore` excludes `.env`.
2. Validate and start the services:

```sh
docker compose config --quiet
docker compose up -d --wait
docker compose ps
```

3. Open [pgAdmin](http://localhost:8085), or the port chosen in `.env`. If the page is still starting, wait briefly and refresh.
4. Sign in using `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD`. Register a PostgreSQL server using host `postgres`, port `5432`, and the database credentials from `.env`.

Follow the [walkthrough](../../weeks/02-postgresql-and-ingestion/part-2-postgres-and-pgadmin.md) for verification queries, persistence, and troubleshooting.

### What does `docker compose config --quiet` do?

It checks whether the Compose configuration is valid without starting any containers. Docker reads `compose.yaml`, substitutes values from `.env`, and checks the resulting configuration. `--quiet` suppresses the configuration that Docker would otherwise print.

- **No output:** validation passed.
- **An error message:** something needs fixing, such as invalid YAML or a required variable missing from `.env`. Fix it before starting the services.

This command does not verify that passwords work, ports are available, or applications will start successfully.

### Connections and storage

PostgreSQL is accessible within the Compose network; its port is not published on the host. pgAdmin is published only on the local loopback interface. This lab uses an administrative PostgreSQL account for learning; deployment environments need separately scoped application accounts.

Stop the services and remove their containers with `docker compose down`. Named volumes retain the database and pgAdmin settings. The walkthrough explains an optional destructive reset separately.

Configuration written independently for DENG. References: [PostgreSQL image](https://hub.docker.com/_/postgres), [pgAdmin container deployment](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html), and [Compose readiness dependencies](https://docs.docker.com/compose/how-tos/startup-order/).

### What does `docker compose build ingest` do?

`ingest` is the Python service defined in `compose.yaml`. Its `build: .` setting tells Docker to use the `Dockerfile` in this directory.

The command prepares a Docker **image** by starting with Python, installing the libraries listed in `requirements.lock`, and copying our Python scripts and SQL files into that image. It does not run the loader, start PostgreSQL, or load any records.

After the image is built successfully, `docker compose run --rm ingest ingest.py data/yellow_tripdata_2024-01.parquet` creates a container from it and runs the Python loader. Rebuild after editing the scripts so the image contains your changes.

### Ingestion file guide

If you already created `taxi_trips` from the earlier draft containing an added row-number column, remove just that obsolete column once in pgAdmin before using the updated loader:

```sql
ALTER TABLE public.taxi_trips DROP COLUMN IF EXISTS source_row_number;
```

This removes that column and its primary-key constraint while preserving the trip fields and rows. Fresh tables created from the current schema need no adjustment.

Step 1 runs locally: follow the [Python and file preparation](../../preparation/week-02.md), then run `.venv/bin/python inspect_source.py data/yellow_tripdata_2024-01.parquet` from this directory (Windows: `.\.venv\Scripts\python.exe` instead of `.venv/bin/python`). The file-path argument is required. The script reads your saved file without downloading or deleting it, and needs only PyArrow. Docker is used in the later ingestion step.

| Step | File |
|---|---|
| Inspect a local file | [inspect_source.py](inspect_source.py); install [requirements-inspect.txt](requirements-inspect.txt) before class |
| Create the empty destination table | Execute the statement in [sql/schema.sql](sql/schema.sql) in pgAdmin; verify its columns and zero rows before loading. See [Step 2](../../weeks/02-postgresql-and-ingestion/part-3-python-ingestion.md#step-2--create-an-empty-destination-table). |
| Load with Python | [ingest.py](ingest.py): read, rename, connect, and write up to 10,000 local records |
| Run in Docker | [Dockerfile](Dockerfile) and [compose.yaml](compose.yaml) |
| Verify the result | [sql/verification.sql](sql/verification.sql) |
| Check reruns | [tests/test_pipeline.py](tests/test_pipeline.py) and Part 3's final exercise |

The loader requires the table from Step 2 and a downloaded yellow taxi file in `data/`. Compose mounts that folder read-only. Each run replaces the rows in `taxi_trips`; no source download or metadata table is needed.
