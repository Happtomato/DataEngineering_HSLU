"""Inspect an already-downloaded Parquet file. No Docker or database needed."""

import argparse
from pathlib import Path
from pprint import pprint

import pyarrow.parquet as pq


def inspect_file(file_path):
    """Read metadata and at most five records; leave the file unchanged."""
    with pq.ParquetFile(file_path) as parquet:
        print(f"File: {file_path}")
        print(f"Rows: {parquet.metadata.num_rows:,}")
        print("\nColumns and data types:")
        print(parquet.schema_arrow)

        print("\nFirst five records (not a representative sample):")
        batch = next(parquet.iter_batches(batch_size=5), None)
        if batch is None:
            print("The file contains no records.")
        else:
            for number, record in enumerate(batch.to_pylist(), start=1):
                print(f"\nRecord {number}")
                pprint(record, sort_dicts=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to the downloaded .parquet file")
    args = parser.parse_args()
    if not args.file.is_file():
        parser.error(f"File not found: {args.file}. Check the path and your working directory.")
    try:
        inspect_file(args.file)
    except (OSError, ValueError) as error:
        parser.error(f"Cannot read this Parquet file: {error}")


if __name__ == "__main__":
    main()
