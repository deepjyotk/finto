"""
asyncio examples — from basic to patterns used in this project.
Run any section with:  python asyncio.py
"""

import asyncio
import time


# ─────────────────────────────────────────────
# 1. BASIC: async def + await
# ─────────────────────────────────────────────

async def fetch_price(ticker: str) -> float:
    """Simulates an async HTTP/DB call."""
    print(f"  → fetching {ticker}...")
    await asyncio.sleep(1)          # non-blocking wait (like a real network call)
    print(f"  ← got {ticker}")
    return round(100 + hash(ticker) % 50, 2)


async def basic_example():
    print("\n── 1. Sequential awaits (slow) ──")
    t0 = time.perf_counter()

    price_aapl = await fetch_price("AAPL")  # waits 1 s
    price_msft = await fetch_price("MSFT")  # waits another 1 s

    elapsed = time.perf_counter() - t0
    print(f"AAPL={price_aapl}, MSFT={price_msft}  ({elapsed:.1f}s)")
    # ↑ ~2 seconds — sequential, not concurrent


# ─────────────────────────────────────────────
# 2. CONCURRENT: asyncio.gather()
# ─────────────────────────────────────────────

async def gather_example():
    print("\n── 2. Concurrent with gather() (fast) ──")
    t0 = time.perf_counter()

    prices = await asyncio.gather(
        fetch_price("AAPL"),
        fetch_price("MSFT"),
        fetch_price("GOOGL"),
    )

    elapsed = time.perf_counter() - t0
    tickers = ["AAPL", "MSFT", "GOOGL"]
    for ticker, price in zip(tickers, prices):
        print(f"  {ticker}: {price}")
    print(f"  Total: {elapsed:.1f}s")
    # ↑ ~1 second — all three run at the same time


# ─────────────────────────────────────────────
# 3. TASKS: create_task() — fire and keep working
# ─────────────────────────────────────────────

async def task_example():
    print("\n── 3. create_task() — schedule without blocking ──")

    # Schedule the coroutine; it starts immediately but we don't await yet
    task = asyncio.create_task(fetch_price("TSLA"))

    # Do other work while the task runs in the background
    print("  doing other work while TSLA fetches...")
    await asyncio.sleep(0.2)
    print("  still working...")

    price = await task   # now collect the result
    print(f"  TSLA: {price}")


# ─────────────────────────────────────────────
# 4. ERROR HANDLING in gather()
# ─────────────────────────────────────────────

async def risky_fetch(ticker: str) -> float:
    await asyncio.sleep(0.5)
    if ticker == "BAD":
        raise ValueError(f"No data for {ticker}")
    return 42.0


async def error_handling_example():
    print("\n── 4. Error handling with return_exceptions=True ──")

    results = await asyncio.gather(
        risky_fetch("AAPL"),
        risky_fetch("BAD"),
        risky_fetch("MSFT"),
        return_exceptions=True,   # exceptions become values, not crashes
    )

    for ticker, result in zip(["AAPL", "BAD", "MSFT"], results):
        if isinstance(result, Exception):
            print(f"  {ticker}: ERROR — {result}")
        else:
            print(f"  {ticker}: {result}")


# ─────────────────────────────────────────────
# 5. REAL PATTERN: fan-out batch fetch (used in ticker_service.py)
# ─────────────────────────────────────────────

async def fetch_ticker_data(ticker: str) -> dict:
    """Mirrors what ticker_service does with yfinance/DB calls."""
    await asyncio.sleep(0.3)   # pretend I/O
    return {"ticker": ticker, "price": round(150 + hash(ticker) % 100, 2)}


async def batch_fetch(tickers: list[str], batch_size: int = 5) -> list[dict]:
    """
    Fetch many tickers in controlled batches to avoid overwhelming the API.
    Returns results in the same order as input.
    """
    results = []
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        batch_results = await asyncio.gather(*[fetch_ticker_data(t) for t in batch])
        results.extend(batch_results)
    return results


async def batch_example():
    print("\n── 5. Batched fan-out (real project pattern) ──")
    tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "META"]

    t0 = time.perf_counter()
    data = await batch_fetch(tickers, batch_size=3)
    elapsed = time.perf_counter() - t0

    for d in data:
        print(f"  {d['ticker']}: ${d['price']}")
    print(f"  {len(tickers)} tickers in {elapsed:.1f}s")


# ─────────────────────────────────────────────
# 6. BLOCKING CODE in async context — the right way
# ─────────────────────────────────────────────

def slow_sync_call(ticker: str) -> str:
    """A blocking library call (e.g. yfinance, pandas)."""
    time.sleep(0.5)   # blocks the whole thread if called directly in async
    return f"{ticker}_data"


async def run_in_executor_example():
    print("\n── 6. Offloading blocking code with run_in_executor ──")
    loop = asyncio.get_running_loop()

    # Run sync function in a thread pool so the event loop stays free
    result = await loop.run_in_executor(None, slow_sync_call, "AAPL")
    print(f"  got: {result}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

async def main():
    await basic_example()
    await gather_example()
    await task_example()
    await error_handling_example()
    await batch_example()
    await run_in_executor_example()


if __name__ == "__main__":
    asyncio.run(main())
