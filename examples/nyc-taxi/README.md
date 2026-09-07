# NYC Taxi — local database environment

[Week 2 introduction](../../weeks/02-postgresql-and-ingestion/README.md) · [Part 2 walkthrough](../../weeks/02-postgresql-and-ingestion/part-2-postgres-and-pgadmin.md)

This example currently provides PostgreSQL and pgAdmin. Python ingestion will be added in a later part.

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

PostgreSQL is accessible within the Compose network; its port is not published on the host. pgAdmin is published only on the local loopback interface. This lab uses an administrative PostgreSQL account for learning; deployment environments need separately scoped application accounts.

Stop the services and remove their containers with `docker compose down`. Named volumes retain the database and pgAdmin settings. The walkthrough explains an optional destructive reset separately.

Configuration written independently for DENG. References: [PostgreSQL image](https://hub.docker.com/_/postgres), [pgAdmin container deployment](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html), and [Compose readiness dependencies](https://docs.docker.com/compose/how-tos/startup-order/).
