"""Entrypoint for the demo market-data producer.

Run with ``make demo-us-stocks-producer`` (or ``uv run python -m
src.demo_us_stocks_data_engineering``).
"""

from pathlib import Path

from dotenv import load_dotenv

# Load `finto/.env` before importing `src.*`, because `src.core.settings`
# instantiates its settings objects at import time.
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_file, override=True)

from src.core.json_logging import setup_json_logging  # noqa: E402
from src.demo_us_stocks_data_engineering.producer import main  # noqa: E402

if __name__ == "__main__":
    setup_json_logging()
    main()
