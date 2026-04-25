"""Import bridge for price-bars ingest service module under cron-jobs path."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_INGEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "cron-jobs"
    / "price-bars-1d"
    / "services"
    / "price_bars_1d_ingest.py"
)
_SPEC = importlib.util.spec_from_file_location("price_bars_1d_ingest", _INGEST_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Unable to load ingest module from {_INGEST_PATH}")

_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD
_SPEC.loader.exec_module(_MOD)

PriceBars1DIngestService = _MOD.PriceBars1DIngestService
