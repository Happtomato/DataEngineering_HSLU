# Week 2 — Part 1: From Source to Query

## Slide 1 — The problem

A team wants to analyse NYC taxi trips by:

- date;
- pickup and drop-off zone;
- trip distance;
- total fare.

The source publishes trip data as downloadable files.

The team wants to load the data into PostgreSQL and analyse it with SQL.

**Question:** What needs to happen between the published file and the first useful query?

---

## Slide 2 — A first architecture

Complete this pipeline with your partner:

```text
NYC TLC source
      |
      v
________________________
      |
      v
________________________
      |
      v
________________________
```

For every stage, decide:

- What is its responsibility?
- Who initiates the interaction?
- What data enters and leaves the stage?
- How could the stage fail?

---

## Slide 3 — Look at the data before loading it

Inspect a sample of the NYC Taxi data and its data dictionary.

Discuss:

- What does one row represent?
- Which columns are essential for the stated analysis?
- Which columns contain dates, identifiers, or measures?
- Which values might be missing, invalid, or surprising?
- What should the destination table be called?
- What does **successful ingestion** mean?

Write one sentence defining the grain of the destination table.

> Example form: “One row in `________________` represents __________________.”

---

## Slide 4 — Your activity

With your partner, produce:

1. a pipeline diagram;
2. a responsibility for every component;
3. a definition of the destination table grain;
4. three possible ingestion risks;
5. two checks that would show whether ingestion worked.

You have **10 minutes**.

Be ready to explain one decision you made and one alternative you rejected.

---

## Slide 5 — Debrief: the implementation we will build

A minimal local version will contain these roles:

```text
NYC TLC source
      |
      v
Python ingestion program
      |
      v
PostgreSQL database
      |
      v
pgAdmin / SQL queries
```

- **Python** moves data from the source to the database.
- **PostgreSQL** stores the ingested data and executes SQL queries.
- **pgAdmin** is a graphical client for inspecting PostgreSQL.
- **Docker** provides reproducible services and their runtime environment.
- **Docker networking** allows containers to communicate using service names.

Next: [Start PostgreSQL and connect with pgAdmin](part-2-postgres-and-pgadmin.md). We will verify the database before writing the ingestion step.
