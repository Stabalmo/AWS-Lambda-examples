#!/usr/bin/env bash
set -euo pipefail

: "${API_URL:?Set API_URL, e.g. https://xxxxx.execute-api.us-east-1.amazonaws.com/dev}"
: "${AUTH_TOKEN:?Set AUTH_TOKEN to the bearer token value}"

echo "==> Health"
curl -sS "$API_URL/health"
echo

echo "==> Create"
CREATE_JSON="$(curl -sS -X POST "$API_URL/items" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"integration-test"}')"
echo "$CREATE_JSON"

ITEM_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["item"]["id"])' <<<"$CREATE_JSON")"

echo "==> Get $ITEM_ID"
curl -sS "$API_URL/items/$ITEM_ID" -H "Authorization: Bearer $AUTH_TOKEN"
echo

echo "==> Delete $ITEM_ID"
curl -sS -X DELETE "$API_URL/items/$ITEM_ID" -H "Authorization: Bearer $AUTH_TOKEN" -i
echo

echo "OK"


