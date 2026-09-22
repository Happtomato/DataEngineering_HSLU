# Week 5 — Downloads before class

[All preparation checklists](README.md) · [Week 5 materials](../weeks/05-workflow-orchestration/README.md)

This week we will use **Kestra** to coordinate our existing taxi pipeline. Kestra will run in Docker and provide an interface in your browser. You do not need to install Kestra directly on your laptop or create a cloud account.

Complete these downloads on the computer you will bring to class. We will configure and start Kestra and build our first workflow together in class.

## 1. Keep your existing environment and files

Keep the environment from [Week 2](week-02.md) and [Week 4](week-04.md): Docker, the PostgreSQL and pgAdmin images, the ingestion image, your `.env`, and the saved database volumes.

Keep these files in `examples/nyc-taxi/data/`:

- `yellow_tripdata_2024-01.parquet`
- `yellow_tripdata_2024-02.parquet`
- `taxi_zone_lookup.csv`

If any file is missing, follow the linked preparation checklist to download it. No additional dataset is needed for Week 5. Do not run `docker compose down -v`, because it removes the saved database volumes.

Update your course files using your usual Git workflow or the repository's **Code → Download ZIP** option. Preserve your own changes and downloaded data.

## 2. Start Docker

Open Docker Desktop or start your Docker engine. In Terminal on macOS/Linux or PowerShell on Windows, run:

```sh
docker version
docker compose version
```

**Ready when:** Docker reports both a Client and a Server without a connection error, and Compose reports its version.

## 3. Download the images

Run these commands separately. They work from any directory and do not require a new Compose file or an `.env` file:

```sh
docker pull kestra/kestra:v1.1
docker pull postgres:18.6-bookworm
```

| Image | Purpose |
|---|---|
| `kestra/kestra:v1.1` | The workflow application and its browser interface. |
| `postgres:18.6-bookworm` | A separate PostgreSQL service for Kestra's internal metadata, such as workflow definitions and execution state. |

The PostgreSQL image is the same one used in Week 2; Docker can reuse the existing download. In class, we will use it to create a separate service with its own storage. Your taxi database remains separate from Kestra's internal database.

These commands only download images. They do not start Kestra or PostgreSQL, change your existing database, or run ingestion. Allow time for the downloads to finish; Kestra's image may take several minutes depending on your connection.

Use the version shown above so everyone has the same Kestra environment for class.

## 4. Check that the images are available

Run these commands separately:

```sh
docker image inspect kestra/kestra:v1.1 --format '{{.Id}}'
docker image inspect postgres:18.6-bookworm --format '{{.Id}}'
```

**Ready when:** each command prints an identifier beginning with `sha256:`. A “No such image” error means the corresponding image is not available locally; retry its download. These checks verify the downloads, not a running Kestra installation.

You may close Docker Desktop afterward. Keep the images and start Docker again at the beginning of class.

## Ready-to-attend checklist

- [ ] Docker starts and Compose is available.
- [ ] Both image checks print an image ID.
- [ ] I have kept the existing database volumes and ingestion image.
- [ ] The January and February taxi files and zone lookup CSV are in `examples/nyc-taxi/data/`.
- [ ] I have the current course files.

You do not need to start Kestra, create a workflow, run SQL, or reload taxi data before class. Follow the [Week 5 startup instructions](../weeks/05-workflow-orchestration/README.md) in class; the download commands above can be completed independently.

If a check fails, send the instructor your operating system, the command, and its error before class. Do not include passwords or `.env` contents.
