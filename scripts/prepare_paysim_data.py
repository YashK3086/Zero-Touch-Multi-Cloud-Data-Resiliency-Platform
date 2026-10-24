"""Pre-stages and splits the PaySim Kaggle financial dataset (493 MB, 6.36M rows)
into compressed Parquet / Gzip chunks locally, creating:
1. Baseline load chunk (e.g. 500,000 to 1,000,000 rows) for instant COPY INTO upon terraform apply.
2. Streaming drill chunks for continuous real-time ingestion simulation during the failover drill.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger("prepare_paysim_data")

DEFAULT_SOURCE = r"C:\Users\yashv\Downloads\archive (5)\PS_20174392719_1491204439457_log.csv"
OUTPUT_DIR = Path("data/paysim_staged")


def prepare_data(source_csv: str, baseline_rows: int = 500000, stream_chunk_rows: int = 50000, max_chunks: int = 10) -> None:
    source_path = Path(source_csv)
    if not source_path.exists():
        logger.error("Source CSV file not found: %s", source_csv)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Reading PaySim CSV: %s (Size: %.2f MB)", source_csv, source_path.stat().st_size / (1024 * 1024))

    # Read baseline chunk
    t0 = time.time()
    logger.info("Extracting %d rows for baseline primary table...", baseline_rows)
    df_baseline = pd.read_csv(source_path, nrows=baseline_rows)
    baseline_out = OUTPUT_DIR / f"paysim_baseline_{baseline_rows}_rows.parquet"
    df_baseline.to_parquet(baseline_out, compression="snappy", index=False)
    logger.info("Baseline saved to: %s (Size: %.2f MB, Rows: %d, Time: %.2fs)", baseline_out, baseline_out.stat().st_size / (1024 * 1024), len(df_baseline), time.time() - t0)

    # Read streaming drill chunks (for real-time micro-batch ingestion during failover drill)
    logger.info("Preparing streaming drill chunks (%d rows each)...", stream_chunk_rows)
    stream_dir = OUTPUT_DIR / "streaming_chunks"
    stream_dir.mkdir(parents=True, exist_ok=True)

    reader = pd.read_csv(source_path, skiprows=range(1, baseline_rows + 1), chunksize=stream_chunk_rows)
    for i, chunk in enumerate(reader, start=1):
        if i > max_chunks:
            break
        chunk_file = stream_dir / f"drill_stream_chunk_{i:03d}.parquet"
        chunk.to_parquet(chunk_file, compression="snappy", index=False)
        logger.info("Chunk %d/%d written: %s (%d rows)", i, max_chunks, chunk_file.name, len(chunk))

    total_files = len(list(OUTPUT_DIR.glob("**/*.parquet")))
    logger.info("Data preparation complete! Total Parquet files prepared: %d in %s", total_files, OUTPUT_DIR)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Prepare PaySim financial dataset for Snowflake DR drills")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Path to PaySim CSV")
    parser.add_argument("--baseline-rows", type=int, default=500000, help="Initial baseline rows")
    parser.add_argument("--stream-chunk-rows", type=int, default=50000, help="Rows per drill stream batch")
    parser.add_argument("--max-chunks", type=int, default=10, help="Max stream chunks to generate")

    args = parser.parse_args(argv)
    prepare_data(
        source_csv=args.source,
        baseline_rows=args.baseline_rows,
        stream_chunk_rows=args.stream_chunk_rows,
        max_chunks=args.max_chunks,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
