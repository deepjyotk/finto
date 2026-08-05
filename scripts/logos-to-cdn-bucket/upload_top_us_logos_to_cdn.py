#!/usr/bin/env python3
"""Upload logos for the top 300 US companies (by market cap) to GCS + Cloudflare R2.

Universe: Nasdaq.com stock screener download (United States only), ranked by
marketCap, truncated to ``--limit`` (default 300).

Logo source: Financial Modeling Prep US PNG (no ``.NS`` suffix):
  https://financialmodelingprep.com/image-stock/{SYMBOL}.png

Object keys match the India CDN convention so the chat UI probe works:
  {SYMBOL}.png  (frontend tries .svg then .png)

Required env (same as logos-to-cdn-bucket.py):
  GCS_BUCKET_NAME, GCS_PROJECT_ID
  CLOUDFLARE_R2_ACCOUNT_ID, CLOUDFLARE_R2_ACCESS_KEY_ID,
  CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET_NAME

Usage:
    # Upload top 300
    uv run python scripts/logos-to-cdn-bucket/upload_top_us_logos_to_cdn.py

    # Preview ranking only
    uv run python scripts/logos-to-cdn-bucket/upload_top_us_logos_to_cdn.py --dry-run

    # Smaller batch
    uv run python scripts/logos-to-cdn-bucket/upload_top_us_logos_to_cdn.py --limit 50
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from google.api_core.exceptions import GoogleAPICallError

_FINTO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_FINTO_ROOT / ".env")


def _load_cdn_upload_helpers():
    """Load helpers from logos-to-cdn-bucket.py (hyphenated filename)."""
    path = _SCRIPT_DIR / "logos-to-cdn-bucket.py"
    spec = importlib.util.spec_from_file_location("logos_to_cdn_bucket", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_cdn = _load_cdn_upload_helpers()
_ensure_gcs_bucket = _cdn._ensure_gcs_bucket
_gcs_client = _cdn._gcs_client
_r2_client = _cdn._r2_client
upload_to_gcs = _cdn.upload_to_gcs
upload_to_r2 = _cdn.upload_to_r2

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
NASDAQ_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableonly=true&limit=0&offset=0&download=true"
)
FMP_US_LOGO_URL = "https://financialmodelingprep.com/image-stock/{symbol}.png"


def _parse_market_cap(raw: str | None) -> float:
    """Parse Nasdaq marketCap strings like '39314526605.00' or '$1.2T'."""
    if raw is None:
        return 0.0
    s = str(raw).replace("$", "").replace(",", "").strip()
    if not s or s.upper() in {"NA", "N/A", "--", "NULL"}:
        return 0.0
    mult = 1.0
    if s[-1].upper() in {"K", "M", "B", "T"} and not s[-1].isdigit():
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[s[-1].upper()]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def fetch_top_us_by_market_cap(
    *,
    limit: int,
    user_agent: str,
    timeout: float,
) -> list[tuple[str, float, str]]:
    """Return [(symbol, market_cap, name), ...] for United States issuers only."""
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json,text/plain,*/*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(NASDAQ_SCREENER_URL)
        resp.raise_for_status()
        payload = resp.json()

    rows = ((payload.get("data") or {}).get("rows")) or []
    ranked: list[tuple[str, float, str]] = []
    seen: set[str] = set()
    for row in rows:
        country = str(row.get("country") or "").strip().lower()
        if country not in {"united states", "usa", "us"}:
            continue
        raw_sym = str(row.get("symbol") or "").strip().upper()
        # Skip warrants / units / preferred-looking suffixes common in this feed
        if not raw_sym or "/" in raw_sym or "^" in raw_sym:
            continue
        if raw_sym.endswith(("W", "U", "R")) and len(raw_sym) > 5:
            continue
        sym = raw_sym.replace(".", "-")
        if sym in seen:
            continue
        cap = _parse_market_cap(row.get("marketCap"))
        if cap <= 0:
            continue
        name = str(row.get("name") or "").strip()
        seen.add(sym)
        ranked.append((sym, cap, name))

    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked[:limit]


def fetch_fmp_us_logo_png_bytes(symbol_upper: str, *, user_agent: str, timeout: float) -> bytes:
    """Fetch US (no .NS) company logo PNG from Financial Modeling Prep."""
    url = FMP_US_LOGO_URL.format(symbol=symbol_upper)
    headers = {
        "accept": "image/png,image/*,*/*;q=0.8",
        "user-agent": user_agent,
    }
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url, headers=headers)
        r.raise_for_status()
    data = r.content
    if len(data) < len(PNG_MAGIC) or not data.startswith(PNG_MAGIC):
        raise ValueError(
            "FMP US logo response is not a PNG "
            f"(content-type={r.headers.get('content-type')!r}, head={data[:24]!r})"
        )
    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload logos for top US companies (by market cap) to GCS + R2 CDN.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=300,
        help="How many top companies to upload (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print ranked symbols; do not fetch/upload logos",
    )
    parser.add_argument(
        "--gcs-only",
        action="store_true",
        help="Upload only to GCS (skip Cloudflare R2). Useful when R2 env vars are unset.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between logo fetches (default: 0.2)",
    )
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.limit <= 0:
        print("error: --limit must be > 0", file=sys.stderr)
        sys.exit(1)

    # Defaults match production logo bucket when unset in local .env
    os.environ.setdefault("GCS_BUCKET_NAME", "finto-logos")
    os.environ.setdefault("GCS_PROJECT_ID", "finto-477904")

    ranked = fetch_top_us_by_market_cap(
        limit=args.limit,
        user_agent=args.user_agent,
        timeout=args.timeout,
    )
    if not ranked:
        print("error: no ranked US symbols resolved", file=sys.stderr)
        sys.exit(1)

    print(f"\nTop {len(ranked)} US companies by market cap:", file=sys.stderr)
    for i, (sym, cap, name) in enumerate(ranked, 1):
        print(f"  {i:3d}. {sym:<8}  ${cap:,.0f}  {name[:50]}")

    if args.dry_run:
        print("\nDry run — no uploads.", file=sys.stderr)
        return

    required = ["GCS_BUCKET_NAME"]
    if not args.gcs_only:
        required.extend(
            [
                "CLOUDFLARE_R2_ACCOUNT_ID",
                "CLOUDFLARE_R2_ACCESS_KEY_ID",
                "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
                "CLOUDFLARE_R2_BUCKET_NAME",
            ]
        )
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"error: missing env vars: {', '.join(missing)}", file=sys.stderr)
        if not args.gcs_only:
            print(
                "hint: add R2 keys to .env, or re-run with --gcs-only to upload GCS only",
                file=sys.stderr,
            )
        sys.exit(1)

    gcs_client = _gcs_client()
    gcs_bucket = _ensure_gcs_bucket(gcs_client, os.environ["GCS_BUCKET_NAME"])
    r2 = None
    r2_bucket = ""
    if not args.gcs_only:
        r2 = _r2_client()
        r2_bucket = os.environ["CLOUDFLARE_R2_BUCKET_NAME"]

    ok = 0
    failed = 0
    for sym, _cap, _name in ranked:
        try:
            data = fetch_fmp_us_logo_png_bytes(
                sym, user_agent=args.user_agent, timeout=args.timeout
            )
            blob_name = f"{sym}.png"
            gcs_uri = upload_to_gcs(gcs_bucket, blob_name, data, "image/png")
            if args.gcs_only:
                print(f"OK {sym} [fmp-us] → {gcs_uri}")
            else:
                r2_uri = upload_to_r2(r2, r2_bucket, blob_name, data, "image/png")
                print(f"OK {sym} [fmp-us] → {gcs_uri} | {r2_uri}")
            ok += 1
        except (
            httpx.HTTPError,
            ValueError,
            json.JSONDecodeError,
            GoogleAPICallError,
            BotoCoreError,
            ClientError,
        ) as exc:
            print(f"FAIL {sym}: {exc}", file=sys.stderr)
            failed += 1
        time.sleep(args.sleep)

    print(f"\nDone: {ok} uploaded, {failed} failed (of {len(ranked)})", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
