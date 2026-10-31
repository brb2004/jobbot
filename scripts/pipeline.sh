#!/usr/bin/env bash
# crawl -> requirements -> score. Run every 2 days.
set -euo pipefail
cd "$(dirname "$0")/../backend"
source .venv/bin/activate
echo "=== $(date -Is) pipeline start"
python -m app.ingest.run_ingest
python -m app.llm.run_scoring 20
echo "=== $(date -Is) pipeline done"
