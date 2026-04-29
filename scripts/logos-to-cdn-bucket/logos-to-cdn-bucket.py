#!/usr/bin/env python3
"""Upload company logos to GCS bucket and Cloudflare R2 (free-tier CDN).

Fetches logos using the same Multibagg SVG → FMP PNG fallback strategy as
fetch_multibagg_company_logo_svg.py, but instead of writing to disk the bytes
are uploaded directly to:
  - Google Cloud Storage (origin / backup)
  - Cloudflare R2 (S3-compatible, free-tier CDN delivery)

Required environment variables (see .env.example):
  GCS_BUCKET_NAME, GCS_PROJECT_ID
  CLOUDFLARE_R2_ACCOUNT_ID, CLOUDFLARE_R2_ACCESS_KEY_ID,
  CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME

Usage:
    # Single symbol
    python scripts/logos-to-cdn-bucket/logos-to-cdn-bucket.py RELIANCE

    # All symbols from DB
    python scripts/logos-to-cdn-bucket/logos-to-cdn-bucket.py --from-in-equities

    # First 50 symbols from DB
    python scripts/logos-to-cdn-bucket/logos-to-cdn-bucket.py --from-in-equities --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from typing import Any

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage as gcs

# ── Bootstrap ──────────────────────────────────────────────────────────────

_FINTO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_FINTO_ROOT / ".env")

# Import logo-fetching helpers from the sibling script (no code duplication).
sys.path.insert(0, str(Path(__file__).parent))
from fetch_multibagg_company_logo_svg import (  # noqa: E402
    DEFAULT_REFERER,
    DEFAULT_UA,
    fetch_fmp_logo_png_bytes,
    fetch_logo_svg_bytes,
    fetch_symbols_from_in_equities,
)


# ── GCS helpers ────────────────────────────────────────────────────────────


def _gcs_client() -> Any:
    project = os.environ.get("GCS_PROJECT_ID", "finto-477904")
    return gcs.Client(project=project)


def _ensure_gcs_bucket(client: Any, bucket_name: str) -> Any:
    """Return the bucket, creating it in us-central1 if it doesn't exist."""
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        project = os.environ.get("GCS_PROJECT_ID", "finto-477904")
        bucket = client.create_bucket(bucket_name, project=project, location="us-central1")
        print(
            f"Created GCS bucket '{bucket_name}'. "
            f"Add GCS_BUCKET_NAME={bucket_name} to your .env file.",
            file=sys.stderr,
        )
    return bucket


def upload_to_gcs(
    bucket: Any,
    blob_name: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload bytes to GCS and return the public gs:// URI."""
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{bucket.name}/{blob_name}"


# ── Cloudflare R2 helpers ──────────────────────────────────────────────────


def _r2_client() -> Any:
    account_id = os.environ["CLOUDFLARE_R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["CLOUDFLARE_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CLOUDFLARE_R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def upload_to_r2(
    client: Any,
    bucket_name: str,
    object_key: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload bytes to Cloudflare R2 and return the r2:// URI."""
    client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=data,
        ContentType=content_type,
    )
    public_domain = os.environ.get("CLOUDFLARE_R2_PUBLIC_DOMAIN", "").strip()
    if public_domain:
        return f"https://{public_domain}/{object_key}"
    return f"r2://{bucket_name}/{object_key}"


# ── Logo fetch → upload ────────────────────────────────────────────────────


def _content_type(blob_name: str) -> str:
    return "image/svg+xml" if blob_name.endswith(".svg") else "image/png"


def fetch_and_upload_logo(
    symbol_upper: str,
    gcs_bucket: Any,
    r2_client: Any,
    r2_bucket: str,
    *,
    referer: str,
    user_agent: str,
    timeout: float,
) -> tuple[str, str, str]:
    """
    Fetch logo bytes (Multibagg SVG first, FMP PNG on failure) and upload to
    both GCS and Cloudflare R2.

    Returns (gcs_uri, r2_uri, source) where source is ``multibagg`` or ``fmp``.
    """
    try:
        data = fetch_logo_svg_bytes(
            symbol_upper, referer=referer, user_agent=user_agent, timeout=timeout
        )
        blob_name = f"{symbol_upper}.svg"
        source = "multibagg"
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        data = fetch_fmp_logo_png_bytes(symbol_upper, user_agent=user_agent, timeout=timeout)
        blob_name = f"{symbol_upper}.png"
        source = "fmp"

    ctype = _content_type(blob_name)
    gcs_uri = upload_to_gcs(gcs_bucket, blob_name, data, ctype)
    r2_uri = upload_to_r2(r2_client, r2_bucket, blob_name, data, ctype)
    return gcs_uri, r2_uri, source


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch company logos (Multibagg SVG → FMP PNG fallback) and upload "
            "to GCS and Cloudflare R2."
        ),
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="Ticker symbol for single upload (ignored when --from-in-equities is set)",
    )
    parser.add_argument(
        "--from-in-equities",
        action="store_true",
        help="Load symbols from Postgres in_equities (ordered by symbol); upload each logo.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="With --from-in-equities: max symbols to process (default: all)",
    )
    parser.add_argument("--referer", default=DEFAULT_REFERER)
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    # Validate required env vars early.
    missing = [
        v
        for v in (
            "GCS_BUCKET_NAME",
            "CLOUDFLARE_R2_ACCOUNT_ID",
            "CLOUDFLARE_R2_ACCESS_KEY_ID",
            "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
            "CLOUDFLARE_R2_BUCKET_NAME",
        )
        if not os.environ.get(v)
    ]
    if missing:
        print(f"error: missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    gcs_client = _gcs_client()
    gcs_bucket = _ensure_gcs_bucket(gcs_client, os.environ["GCS_BUCKET_NAME"])
    r2 = _r2_client()
    r2_bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]

    upload_kwargs = dict(
        gcs_bucket=gcs_bucket,
        r2_client=r2,
        r2_bucket=r2_bucket,
        referer=args.referer,
        user_agent=args.user_agent,
        timeout=args.timeout,
    )

    if args.from_in_equities:
        try:
            symbols = asyncio.run(fetch_symbols_from_in_equities(args.limit))
        except Exception as exc:
            print(f"error: DB: {exc}", file=sys.stderr)
            sys.exit(1)

        if not symbols:
            print("error: no rows returned from in_equities", file=sys.stderr)
            sys.exit(1)

        failed = 0
        for sym in symbols:
            sym_upper = sym.upper().strip()
            try:
                gcs_uri, r2_uri, src = fetch_and_upload_logo(sym_upper, **upload_kwargs)
                print(f"OK {sym_upper} [{src}] → {gcs_uri} | {r2_uri}")
            except (
                httpx.HTTPError,
                ValueError,
                json.JSONDecodeError,
                GoogleAPICallError,
                BotoCoreError,
                ClientError,
            ) as exc:
                print(f"FAIL {sym_upper}: {exc}", file=sys.stderr)
                failed += 1

        sys.exit(1 if failed else 0)

    symbol_upper = (args.symbol or "SPLPETRO").upper()
    try:
        gcs_uri, r2_uri, src = fetch_and_upload_logo(symbol_upper, **upload_kwargs)
    except (
        httpx.HTTPError,
        ValueError,
        json.JSONDecodeError,
        GoogleAPICallError,
        BotoCoreError,
        ClientError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Uploaded [{src}] {gcs_uri} | {r2_uri}")


if __name__ == "__main__":
    main()
