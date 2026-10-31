#!/usr/bin/env bash
# log in and print my dashboard
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"braydenbenard7@gmail.com","password":"pick-a-real-password"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s localhost:8000/dashboard -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
