"""Wait for Mongo, then exec the container CMD (uvicorn)."""

from __future__ import annotations

import os
import sys
import time


def wait_for_mongo(attempts: int = 60, delay: float = 2.0) -> None:
    uri = os.environ.get("MONGO_URI", "mongodb://mongo:27017")
    print(f"Waiting for MongoDB at {uri}…", flush=True)
    last_error: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            from src.db import ping

            ping()
            print("Mongo OK", flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"  attempt {i}/{attempts}: {exc}", flush=True)
            time.sleep(delay)
    raise SystemExit(f"MongoDB not reachable after {attempts} attempts: {last_error}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: entrypoint.py <command> [args...]")
    wait_for_mongo()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
