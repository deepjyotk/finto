#!/usr/bin/env python3
"""Company logos: Multibagg SVG API first; on failure, Financial Modeling Prep PNG (.NS)."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote_to_bytes

import asyncpg
import httpx
from dotenv import load_dotenv

DEFAULT_REFERER = (
    "https://www.multibagg.ai/screener/stocks/predefined-cm77ku2u4000610laavt2d9eu"
)
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

_FINTO_ROOT = Path(__file__).resolve().parents[2]
_SVGS_DIR = _FINTO_ROOT / "svgs"

load_dotenv(_FINTO_ROOT / ".env")

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _svg_bytes_from_data_uri(uri: str) -> bytes:
    if not uri.startswith("data:"):
        raise ValueError("Expected a data: URI with SVG content")

    try:
        comma = uri.index(",")
    except ValueError as exc:
        raise ValueError("Malformed data URI (no comma)") from exc

    meta = uri[5:comma].lower()
    payload = uri[comma + 1 :]

    if "svg" not in meta and "image/svg" not in meta:
        raise ValueError(f"Expected SVG media type in data URI, got meta={meta!r}")

    if ";base64" in meta or "base64" in meta.split(";"):
        return base64.b64decode(payload, validate=False)

    # Percent-encoded SVG after comma
    return unquote_to_bytes(payload.replace("+", "%20"))


def _extract_data_uri_field(parsed: object) -> str:
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, dict):
        for key in ("data", "logo", "url", "src", "image"):
            val = parsed.get(key)
            if isinstance(val, str) and val.startswith("data:"):
                return val
        raise ValueError(
            "JSON object had no recognizable data URI field "
            f"(keys: {list(parsed.keys())})"
        )
    raise ValueError(f"Unexpected JSON root type: {type(parsed).__name__}")


def fetch_logo_svg_bytes(symbol: str, *, referer: str, user_agent: str, timeout: float) -> bytes:
    url = "https://www.multibagg.ai/api/v1/company-logo"
    headers = {
        "accept": "*/*",
        "referer": referer,
        "user-agent": user_agent,
    }
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url, params={"symbol": symbol}, headers=headers)
        r.raise_for_status()

    ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
    body = r.text.lstrip("\ufeff")

    if ctype == "application/json" or body.startswith('"'):
        parsed = json.loads(body)
        uri = _extract_data_uri_field(parsed)
        return _svg_bytes_from_data_uri(uri)

    if "svg" in ctype or body.lstrip().startswith("<svg"):
        return body.encode("utf-8")

    raise ValueError(
        f"Unexpected response content-type={ctype!r}; cannot infer SVG "
        f"(first bytes={body[:120]!r})"
    )


def fmp_logo_png_url(symbol_upper: str) -> str:
    return f"https://financialmodelingprep.com/image-stock/{symbol_upper}.NS.png"


def fetch_fmp_logo_png_bytes(symbol_upper: str, *, user_agent: str, timeout: float) -> bytes:
    url = fmp_logo_png_url(symbol_upper)
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
            "FMP response is not a PNG "
            f"(content-type={r.headers.get('content-type')!r}, head={data[:24]!r})"
        )
    return data


def _default_logo_paths(symbol_upper: str, output_override: Path | None) -> tuple[Path, Path]:
    """Multibagg SVG path and FMP PNG path for this fetch."""
    if output_override is not None:
        svg_path = output_override
        png_path = output_override.with_suffix(".png")
        return svg_path, png_path
    base = _SVGS_DIR / symbol_upper
    return base.with_suffix(".svg"), base.with_suffix(".png")


def save_company_logo_with_fallback(
    symbol_upper: str,
    output_override: Path | None,
    *,
    referer: str,
    user_agent: str,
    timeout: float,
) -> tuple[Path, int, str]:
    """
    Try Multibagg SVG → file; if that fails, try FMP `SYMBOL.NS.png` → PNG file.

    Returns (path_written, nbytes, source) where source is ``multibagg`` or ``fmp``.
    """
    svg_path, png_path = _default_logo_paths(symbol_upper, output_override)

    try:
        svg = fetch_logo_svg_bytes(symbol_upper, referer=referer, user_agent=user_agent, timeout=timeout)
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        png = fetch_fmp_logo_png_bytes(symbol_upper, user_agent=user_agent, timeout=timeout)
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(png)
        return png_path, len(png), "fmp"

    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_bytes(svg)
    return svg_path, len(svg), "multibagg"


def _database_url_sync() -> str:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL is not set (check finto/.env).")
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def fetch_symbols_from_in_equities(limit: int | None = None) -> list[str]:
    """All symbols from in_equities (ORDER BY symbol); pass limit to cap the result set."""
    url = _database_url_sync()
    conn = await asyncpg.connect(url)
    try:
        if limit is None:
            rows = await conn.fetch("SELECT symbol FROM in_equities ORDER BY symbol")
        else:
            rows = await conn.fetch(
                "SELECT symbol FROM in_equities ORDER BY symbol LIMIT $1",
                limit,
            )
        return [r["symbol"] for r in rows]
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch company logo: Multibagg SVG API first; if that fails, "
            "Financial Modeling Prep PNG (image-stock/{SYMBOL}.NS.png)."
        ),
    )
    parser.add_argument(
        "symbol",
        nargs="?",
        default=None,
        help="Ticker symbol for single fetch (ignored when --from-in-equities is set)",
    )
    parser.add_argument(
        "--from-in-equities",
        action="store_true",
        help="Load symbols from Postgres in_equities (ordered by symbol); fetch each logo.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="With --from-in-equities: max rows to process (default: all)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Single-fetch only: preferred Multibagg output .svg path (default: "
            "finto/svgs/<SYMBOL>.svg). On FMP fallback, writes sibling .png "
            "(e.g. SYMBOL.png next to SYMBOL.svg)."
        ),
    )
    parser.add_argument("--referer", default=DEFAULT_REFERER)
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.from_in_equities:
        try:
            symbols = asyncio.run(fetch_symbols_from_in_equities(args.limit))
        except (RuntimeError, OSError, asyncpg.PostgresError) as exc:
            print(f"error: DB: {exc}", file=sys.stderr)
            sys.exit(1)

        if not symbols:
            print("error: no rows returned from in_equities", file=sys.stderr)
            sys.exit(1)

        failed = 0
        for sym in symbols:
            sym_upper = sym.upper().strip()
            try:
                out_path, n, src = save_company_logo_with_fallback(
                    sym_upper,
                    None,
                    referer=args.referer,
                    user_agent=args.user_agent,
                    timeout=args.timeout,
                )
                print(f"OK {sym_upper} [{src}] → {out_path.resolve()} ({n} bytes)")
            except (httpx.HTTPError, ValueError, json.JSONDecodeError, OSError) as exc:
                print(f"FAIL {sym_upper}: {exc}", file=sys.stderr)
                failed += 1

        sys.exit(1 if failed else 0)

    symbol_upper = (args.symbol or "SPLPETRO").upper()
    out_override = args.output

    try:
        out_path, n, src = save_company_logo_with_fallback(
            symbol_upper,
            out_override,
            referer=args.referer,
            user_agent=args.user_agent,
            timeout=args.timeout,
        )
    except (httpx.HTTPError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote [{src}] {out_path.resolve()} ({n} bytes)")


if __name__ == "__main__":
    main()
