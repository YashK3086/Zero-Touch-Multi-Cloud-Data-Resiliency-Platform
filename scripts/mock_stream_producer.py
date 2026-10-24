"""Continuous streaming ingestion mock producer.

Simulates PhonePe/Swiggy order ingestion streaming into S3 stage:
sf-dr-primary-stage-drdemo/incoming/
Generates JSON batches with microsecond timestamps and incrementing sequence IDs
to test and mathematically prove RPO = 0 during mid-flight failover drills.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("mock_stream_producer")


def generate_batch(count: int, start_seq: int) -> list[dict]:
    merchants = ["SWIGGY_INSTAMART", "PHONEPE_MERCHANT_QR", "ZOMATO_DELIVERY", "AMAZON_PAY_UPI"]
    cities = ["BLR", "BOM", "DEL", "HYD", "MAA"]
    batch = []
    now = datetime.now(timezone.utc).isoformat()
    for i in range(count):
        batch.append(
            {
                "transaction_id": str(uuid.uuid4()),
                "sequence_num": start_seq + i,
                "timestamp": now,
                "merchant": merchants[(start_seq + i) % len(merchants)],
                "city": cities[(start_seq + i) % len(cities)],
                "amount": round(50.0 + ((start_seq + i) * 13.37 % 1500.0), 2),
                "currency": "INR",
                "status": "SETTLED",
            }
        )
    return batch


def stream_to_s3(
    bucket: str,
    prefix: str,
    rate_per_sec: int = 50,
    interval_seconds: float = 2.0,
    duration_seconds: int | None = None,
    dry_run: bool = False,
) -> int:
    try:
        import boto3
    except ImportError:
        logger.error("boto3 is not installed. Install via pip install boto3 or run in dry-run mode.")
        if not dry_run:
            return 1

    s3_client = None if dry_run else boto3.client("s3")
    seq = 1
    total_written = 0
    batch_size = int(rate_per_sec * interval_seconds)
    start_time = time.time()

    logger.info(
        "Starting mock stream producer: bucket=%s prefix=%s rate=%d/s batch_size=%d dry_run=%s",
        bucket,
        prefix,
        rate_per_sec,
        batch_size,
        dry_run,
    )

    try:
        while True:
            records = generate_batch(batch_size, seq)
            payload = "\n".join(json.dumps(r) for r in records)
            batch_id = f"batch_{int(time.time())}_{seq:08d}.json"
            s3_key = f"{prefix.strip('/')}/{batch_id}"

            if dry_run:
                logger.info("[DRY-RUN] Emitted %d transactions (seq %d-%d) -> %s", len(records), seq, seq + len(records) - 1, s3_key)
            else:
                s3_client.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=payload.encode("utf-8"),
                    ContentType="application/x-ndjson",
                )
                logger.info("Wrote %d transactions to s3://%s/%s (seq: %d-%d)", len(records), bucket, s3_key, seq, seq + len(records) - 1)

            seq += len(records)
            total_written += len(records)

            if duration_seconds and (time.time() - start_time) >= duration_seconds:
                logger.info("Target duration %d reached. Exiting stream producer.", duration_seconds)
                break

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Stream producer interrupted by user. Total emitted: %d transactions.", total_written)

    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Continuous streaming mock transaction generator into S3")
    parser.add_argument("--bucket", default=os.getenv("AWS_S3_BUCKET", "sf-dr-primary-stage-drdemo"))
    parser.add_argument("--prefix", default="incoming/")
    parser.add_argument("--rate", type=int, default=50, help="Transactions per second")
    parser.add_argument("--interval", type=float, default=2.0, help="Batch push interval in seconds")
    parser.add_argument("--duration", type=int, default=None, help="Stop after N seconds (default: run forever)")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without uploading to S3")

    args = parser.parse_args(argv)
    return stream_to_s3(
        bucket=args.bucket,
        prefix=args.prefix,
        rate_per_sec=args.rate,
        interval_seconds=args.interval,
        duration_seconds=args.duration,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
