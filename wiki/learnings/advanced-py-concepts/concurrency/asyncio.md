# asyncio – Concurrency in Python

## What problem does it solve?

Most programs spend time *waiting* — for a database, an HTTP response, a file read.
Threads solve this but are expensive. `asyncio` solves it with a **single thread** that
switches between tasks whenever one is blocked on I/O.

```
Thread model        asyncio model
──────────────      ──────────────────────────
Thread 1 ──wait──  Task A ──await──╮  (event loop picks up Task B)
Thread 2 ──wait──  Task B ──await──╯  (event loop picks up Task A)
...                (single OS thread, zero context-switch overhead)
```

## Key vocabulary


| Term                    | Meaning                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------- |
| `async def`             | Declares a **coroutine** function. Calling it returns a coroutine object (not a result).        |
| `await`                 | Suspends the current coroutine until the awaited thing finishes. Only valid inside `async def`. |
| **Event loop**          | The scheduler that drives all coroutines. `asyncio.run()` creates and tears one down.           |
| `asyncio.gather()`      | Run multiple coroutines **concurrently** and wait for all results.                              |
| `asyncio.create_task()` | Schedule a coroutine to run soon without waiting for it immediately.                            |
| `asyncio.sleep()`       | Non-blocking pause — yields control back to the event loop.                                     |


## When to use asyncio vs threads vs multiprocessing


| Workload                                       | Best tool                                       |
| ---------------------------------------------- | ----------------------------------------------- |
| Many I/O-bound tasks (HTTP, DB, files)         | **asyncio**                                     |
| Blocking libraries that don't support async    | `ThreadPoolExecutor` via `loop.run_in_executor` |
| CPU-heavy work (ML, parsing, number crunching) | `multiprocessing` / `ProcessPoolExecutor`       |


## Gotchas

1. **Blocking calls freeze the loop** — never call `time.sleep()`, `requests.get()`, or any
  sync I/O directly inside a coroutine. Use async equivalents (`asyncio.sleep`, `httpx`,
   `asyncpg`, etc.) or offload with `run_in_executor`.
2. `**await` doesn't mean parallel** — two `await` calls in sequence still run one after
  the other. Use `gather()` or `create_task()` for true concurrency.
3. **One event loop per thread** — `asyncio.run()` creates a fresh loop. Don't call it
  inside an already-running loop (common mistake in Jupyter / FastAPI handlers).
4. **Exceptions in tasks are silent** unless you `await` the task or attach a callback.

## Relation to this project

- FastAPI routes are coroutines — `async def` handlers run on uvicorn's event loop.
- Database calls use `asyncpg` / SQLAlchemy async — always `await` them.
- `asyncio.gather()` is used to fan out multiple ticker fetches simultaneously in
`ticker_service.py` and `screener_tool.py`.





## Personal Notes

- Asked: *What is asyncio loop? Is it like a new thread?*
- Key takeaway:
  - ❌ Not a new thread
  - ✅ **Event loop = scheduler running in one thread**
  - Runs multiple **coroutines (tasks)**



- Asked: *Is Python single-threaded or multi-threaded?*
- Notes:
  - Python supports threads, but:
    - ❗ **GIL limits true parallel execution**
  - Asyncio:
    - ✅ Single-threaded concurrency
    - ❌ Not parallelism



- Asked: *Is asyncio like Java virtual threads?*
- Notes:
  - ❌ Not the same
  - Asyncio:
    - cooperative (you must `await`)
  - Virtual threads:
    - preemptive (JVM handles scheduling)



- Asked: *Show real example*
- Notes:
  - Threads → multiple OS threads
  - Asyncio → one thread, many tasks
  - `time.sleep()` ❌ blocks
  - `await asyncio.sleep()` ✅ non-blocking



- Asked: *Where is asyncio used?*
- Notes:
  - API aggregation
  - Web scraping
  - Chat systems
  - Backend APIs (FastAPI)
  - AI agents / tool calling



- Asked: *Should we always use asyncio for I/O?*
- Notes:
  - ❌ Not always
  - ✅ Use when:
    - many concurrent I/O operations
  - ❌ Avoid when:
    - few calls
    - CPU-heavy work



- Asked: *Is it like parking/unparking?*
- Notes:
  - Close analogy, but:
    - ❌ Not threads being parked
    - ✅ **coroutines are paused (yielded)**
  - Event loop:
    - waits for OS signals (epoll/kqueue)
    - resumes tasks



> **The event loop tracks a *Task* (which wraps a coroutine), and when that task pauses (`**await`**), the same thread runs another task.**
>
>  **When I/O becomes ready, the OS signals the event loop, and the event loop then schedules the paused task to resume.**



