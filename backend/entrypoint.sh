#!/bin/sh
set -e

python <<'PY'
import os
import socket
import time

host = os.environ.get("DB_HOST", "postgres")
port = int(os.environ.get("DB_PORT", "5432"))
timeout_seconds = 30
start = time.time()

while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"PostgreSQL is available at {host}:{port}")
            break
    except OSError:
        if time.time() - start > timeout_seconds:
            raise RuntimeError(f"Timed out waiting for PostgreSQL at {host}:{port}")
        print(f"Waiting for PostgreSQL at {host}:{port}...")
        time.sleep(1)
PY

exec "$@"
