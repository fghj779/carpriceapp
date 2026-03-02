#!/usr/bin/env bash
set -euo pipefail

python3 -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
