# Week 2 — Downloads before class

[All weeks](README.md) · [Week 2 materials](../weeks/02-postgresql-and-ingestion/README.md)

**Status:** Database downloads and local Step 1 preparation are documented. The Docker ingestion image build has also been verified; full database-loading validation remains pending.

**Last updated:** 7 September 2026. **Latest change:** Step 1 now uses a manually downloaded file and local Python, with no Docker.

Set aside approximately 20–40 minutes on your first setup; download time varies with your connection. Do this on the computer you will bring to class. You only need to install and download here; we will explain the tools and start the database together in class.

## 1. Install Docker and check that it runs

If you already have a working Docker installation, keep it and proceed to the checks below.

Otherwise, download and install Docker Desktop using the [official instructions for your operating system](https://docs.docker.com/get-started/get-docker/). On a Mac, choose the installer matching Apple silicon or Intel. Follow any Windows prerequisite and restart instructions in the installer. Linux users with Docker Engine and its Compose plugin already installed can use that setup.

Start Docker Desktop/the Docker engine. Open Terminal on macOS/Linux or PowerShell on Windows and run:

```sh
docker version
docker compose version
```

**Ready when:** the first command reports both a Client and a Server, without a connection error; the second reports a Compose version. Use a current version supporting `up --wait` in class. No database needs to be running yet.

## 2. Have the course files on your computer

Use the course repository's GitHub **Code → Download ZIP** option and extract it, or use your existing Git checkout. Obtain the latest published files before following this checklist. If you already have local work, keep it; do not overwrite your changes just to update the download checklist.

Open a terminal at the repository root, then run:

```sh
cd examples/nyc-taxi
```

**Ready when:** this directory contains `compose.yaml` and `.env.example`. All commands below run here.

## 3. Download the two application images

```sh
docker compose --env-file .env.example pull postgres pgadmin
```

This downloads the packaged applications specified in `compose.yaml`. It does not start them, create database tables, or run ingestion. `--env-file .env.example` supplies example settings so Docker can read the configuration; you do not need to set up real lab passwords now. We will create your own `.env` in class.

The current image versions are:

| Application image | Version |
|---|---|
| PostgreSQL | `postgres:18.6-bookworm` |
| pgAdmin | `dpage/pgadmin4:9.17` |

Let both downloads finish. “Already exists” or “up to date” is fine: Docker can reuse an image already on your computer. The first download can take several minutes and requires local disk space; follow Docker's system requirements and resolve any low-disk warning before class.

## 4. Check that the images are present

Run these commands separately:

```sh
docker image inspect postgres:18.6-bookworm --format '{{.Id}}'
docker image inspect dpage/pgadmin4:9.17 --format '{{.Id}}'
```

**Ready when:** each command prints an identifier beginning with `sha256:`. A “No such image” error means that download has not completed. These checks do not start containers or contact PostgreSQL.

You may close Docker Desktop afterward. Keep the downloaded images: do not run image-pruning commands before class. Start Docker again at the beginning of the session.

## 5. Prepare local Python for Step 1

Step 1 uses Python on your laptop, independently of Docker. Use Python 3.12 or 3.13. If needed, install it from [python.org](https://www.python.org/downloads/) before continuing. An existing suitable installation is fine.

From `examples/nyc-taxi`, create a local environment and install the one required library. On macOS/Linux:

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-inspect.txt
.venv/bin/python -c "import pyarrow; print(pyarrow.__version__)"
```

On Windows PowerShell:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-inspect.txt
.\.venv\Scripts\python.exe -c "import pyarrow; print(pyarrow.__version__)"
```

Check the version command before creating the environment. If it reports another Python version, select your installed Python 3.12 or 3.13 interpreter instead. If `.venv` already exists with a suitable interpreter, keep it and skip the creation command.

**Ready when:** the last command prints `22.0.0`. There is no need to activate the environment; the commands use its interpreter directly. You do not need pandas, SQLAlchemy, or the ingestion Docker image for this step.

## 6. Download the taxi file once

1. Create a folder named `data` inside `examples/nyc-taxi`, using your file manager.
2. Download [January 2024 yellow taxi records](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet), linked from the [official TLC page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).
3. Save or move it to `examples/nyc-taxi/data/yellow_tripdata_2024-01.parquet`. Keep the `.parquet` extension. If you already downloaded this exact file, reuse it.
4. Save the Yellow Trips Data Dictionary linked on the TLC page for use in class.

**Ready when:** the browser download is complete and the named file is in `data/` with a nonzero size. This checks availability; we will open the file and interpret its contents in class. Download duration depends on your connection.

The inspection script will read this file without deleting or downloading it again. Parquet files and `.venv` are excluded from Git. You do not need to inspect records or write code before class.

## Ready-to-attend checklist

- [ ] Docker starts and `docker version` reports a server.
- [ ] Docker Compose is available.
- [ ] I have the current example files on the laptop I will bring.
- [ ] Both image checks print an image ID.
- [ ] The local Python environment imports PyArrow and prints `22.0.0`.
- [ ] The yellow taxi file is downloaded into `examples/nyc-taxi/data/`.
- [ ] I have the matching data dictionary available.

You do not need to open pgAdmin, register a database, run SQL, or understand Docker networking before class. Those are learning activities in [Part 2](../weeks/02-postgresql-and-ingestion/part-2-postgres-and-pgadmin.md).

## Prepare the Python ingestion image

The local inspection in Step 1 does not need this image. For the later Docker ingestion step, build it before class from `examples/nyc-taxi`:

```sh
docker compose --env-file .env.example build ingest
```

This downloads and installs the Python dependencies into an image and copies the scripts. It does not start PostgreSQL or run ingestion. The command should finish successfully with the image marked as built. Keep the image for class; rebuild only when the code or dependencies change.

The corrected dependency lock and image build were verified on 8 September 2026.

The simplified ingestion script now reuses the downloaded file through a read-only folder mount. Its image build is verified; database-loading validation remains pending. Keep the file in `examples/nyc-taxi/data` for both inspection and loading.


