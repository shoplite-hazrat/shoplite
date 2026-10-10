#!/usr/bin/env bash
# End-to-end smoke test through the public gateway, as a customer would use it.
# Usage: scripts/smoke-test.sh [gateway-url] [mailpit-url]
# Exits non-zero on the first failure. Used locally and (later) in CI.
set -euo pipefail

GATEWAY=${1:-http://localhost:8080}
MAILPIT=${2:-http://localhost:8025}
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }

echo "Smoke test against $GATEWAY"

[[ $(status "$GATEWAY/") == 200 ]] && pass "frontend served" || fail "frontend not served"

PRODUCTS=$(curl -sf "$GATEWAY/api/catalog/v1/products?limit=100") || fail "list products"
PRODUCT_ID=$(echo "$PRODUCTS" | json "next(p['id'] for p in d['items'] if p['stock'] > 0)")
STOCK_BEFORE=$(curl -sf "$GATEWAY/api/catalog/v1/products/$PRODUCT_ID" | json "d['stock']")
pass "catalog lists products (using $PRODUCT_ID, stock $STOCK_BEFORE)"

ORDER=$(curl -sf -X POST "$GATEWAY/api/orders/v1/orders" -H 'content-type: application/json' \
  -d "{\"customerEmail\":\"$EMAIL\",\"items\":[{\"productId\":\"$PRODUCT_ID\",\"quantity\":1}]}") \
  || fail "place order"
ORDER_ID=$(echo "$ORDER" | json "d['id']")
pass "order placed ($ORDER_ID)"

[[ $(curl -sf "$GATEWAY/api/orders/v1/orders/$ORDER_ID" | json "d['status']") == confirmed ]] \
  && pass "order readable by id" || fail "order not readable"

STOCK_AFTER=$(curl -sf "$GATEWAY/api/catalog/v1/products/$PRODUCT_ID" | json "d['stock']")
[[ $STOCK_AFTER -eq $((STOCK_BEFORE - 1)) ]] && pass "stock decremented" || fail "stock $STOCK_BEFORE -> $STOCK_AFTER"

for _ in $(seq 1 30); do
  COUNT=$(curl -sf "$MAILPIT/api/v1/search?query=to:$EMAIL" | json "d['messages_count']")
  [[ $COUNT -ge 1 ]] && break
  sleep 1
done
[[ $COUNT -eq 1 ]] && pass "confirmation email delivered (event flow works)" || fail "no email for $EMAIL"

echo "Security boundary:"
[[ $(status -X POST "$GATEWAY/api/catalog/v1/products/$PRODUCT_ID/reserve" -H 'content-type: application/json' -d '{}') =~ ^40[34]$ ]] \
  && pass "stock reserve not public" || fail "reserve endpoint is public"
[[ $(status -X POST "$GATEWAY/api/catalog/v1/products" -H 'content-type: application/json' -d '{}') =~ ^40[34]$ ]] \
  && pass "product admin not public" || fail "product create is public"
[[ $(status "$GATEWAY/api/orders/v1/orders") =~ ^40[34]$ ]] \
  && pass "order listing not public" || fail "order listing is public"
[[ $(status "$GATEWAY/api/catalog/metrics") == 404 ]] \
  && pass "metrics not public" || fail "metrics endpoint is public"

echo "All smoke tests passed."
