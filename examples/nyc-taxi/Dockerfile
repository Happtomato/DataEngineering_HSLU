FROM python:3.13.11-slim-bookworm
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY inspect_source.py ingest.py ingest_months.py load_zones.py ./
COPY sql ./sql
COPY tests ./tests
RUN useradd --create-home student
USER student
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python"]
CMD ["ingest.py"]
