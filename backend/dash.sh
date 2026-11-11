#!/usr/bin/env bash
# log in and print my dashboard. Needs JOBBOT_EMAIL and JOBBOT_PASSWORD in the environment (never in this file).
set -euo pipefail
: "${JOBBOT_EMAIL:?set JOBBOT_EMAIL}" "${JOBBOT_PASSWORD:?set JOBBOT_PASSWORD}"
API=${JOBBOT_API:-localhost:8000}
TOKEN=$(python3 -c 'import json,os;print(json.dumps({"email":os.environ["JOBBOT_EMAIL"],"password":os.environ["JOBBOT_PASSWORD"]}))' \
  | curl -s -X POST "$API/auth/login?token=1" -H 'Content-Type: application/json' -d @- \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "$API/dashboard" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
