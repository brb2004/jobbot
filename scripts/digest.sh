#!/usr/bin/env bash
# weekly email. Run Monday morning.
set -euo pipefail
cd "$(dirname "$0")/../backend"
source .venv/bin/activate
echo "=== $(date -Is) digest"
python -m app.services.run_digest
