#!/bin/bash
# =============================================================================
# Hermass StrategyQuant Replica - Production Smoke Test
#
# Usage:
#   # Production
#   PASSWORD='...' bash scripts/prod_smoke.sh
#
#   # Custom target
#   BASE_URL=https://quant.superalpha.com.cn FRONTEND_URL=https://quant.superalpha.com.cn \
#     EMAIL=demo@hermass.com PASSWORD=demo1234 bash scripts/prod_smoke.sh
# =============================================================================
set -euo pipefail

BASE_URL="${BASE_URL:-http://quant.superalpha.com.cn}"
FRONTEND_URL="${FRONTEND_URL:-$BASE_URL}"
EMAIL="${EMAIL:-admin@superalpha.com.cn}"
TIMEOUT="${TIMEOUT:-15}"

if [ -z "${PASSWORD:-}" ]; then
  echo "ERROR: PASSWORD environment variable is required."
  echo "Usage: PASSWORD='...' bash scripts/prod_smoke.sh"
  exit 2
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
WARNINGS=""

log_pass() {
  PASS=$((PASS + 1))
  echo -e "${GREEN}PASS${NC} $1"
}

log_fail() {
  FAIL=$((FAIL + 1))
  echo -e "${RED}FAIL${NC} $1"
}

log_warn() {
  WARNINGS="${WARNINGS}\n  - $1"
  echo -e "${YELLOW}WARN${NC} $1"
}

log_info() {
  echo -e "${BLUE}INFO${NC} $1"
}

# Returns HTTP status code for a URL
http_code() {
  curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$@"
}

# Returns response body
curl_body() {
  curl -s --max-time "$TIMEOUT" "$@"
}

echo "=== Hermass Production Smoke Test ==="
echo "Backend:  $BASE_URL"
echo "Frontend: $FRONTEND_URL"
echo "User:     $EMAIL"
echo "Time:     $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
log_info "[1/8] Health check"
status=$(http_code "$BASE_URL/health")
if [ "$status" = "200" ]; then
  log_pass "/health returns 200"
else
  log_fail "/health returned HTTP $status (expected 200)"
fi

health_response=$(curl_body "$BASE_URL/health")
if echo "$health_response" | python3 -c "import sys,json; d=json.load(sys.stdin); c=d.get('checks',{}); sys.exit(0 if d.get('status') == 'healthy' and c.get('database') == c.get('redis') == c.get('celery') == 'ok' else 1)" 2>/dev/null; then
  log_pass "/health dependency checks are ok"
else
  log_fail "/health dependency checks failed: $health_response"
fi

# ---------------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------------
log_info "[2/8] Login"
login_response=$(curl_body -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

if echo "$login_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('access_token') else 1)" 2>/dev/null; then
  ACCESS_TOKEN=$(echo "$login_response" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  log_pass "Login succeeded, token received"
else
  log_fail "Login failed: $login_response"
  # Stop here if we can't authenticate
  echo ""
  echo "========================================"
  echo -e "${RED}Smoke test aborted: cannot authenticate.${NC}"
  echo "Make sure the demo user exists (run backend/scripts/seed_db.py)."
  exit 1
fi

AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"

legacy_login_response=$(curl_body -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=$EMAIL" \
  --data-urlencode "password=$PASSWORD")

if echo "$legacy_login_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('access_token') else 1)" 2>/dev/null; then
  log_pass "Legacy form login also works"
else
  log_fail "Legacy form login failed: $legacy_login_response"
fi

# ---------------------------------------------------------------------------
# 3. /auth/me
# ---------------------------------------------------------------------------
log_info "[3/8] Current user"
me_response=$(curl_body -H "$AUTH_HEADER" "$BASE_URL/api/v1/auth/me")
if echo "$me_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('email') == '$EMAIL' else 1)" 2>/dev/null; then
  log_pass "/auth/me returns correct user"
else
  log_fail "/auth/me failed: $me_response"
fi

# ---------------------------------------------------------------------------
# 4. Strategies (Dashboard / Strategy Builder)
# ---------------------------------------------------------------------------
log_info "[4/8] Strategies list"
strategy_response=$(curl_body -H "$AUTH_HEADER" "$BASE_URL/api/v1/strategies")
status=$(http_code -H "$AUTH_HEADER" "$BASE_URL/api/v1/strategies")
if [ "$status" = "200" ]; then
  log_pass "/strategies returns 200"
else
  log_fail "/strategies returned HTTP $status"
fi
if echo "$strategy_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'items' in d and 'total' in d else 1)" 2>/dev/null; then
  log_pass "/strategies response shape is valid"
else
  log_fail "/strategies response shape invalid: $strategy_response"
fi

# ---------------------------------------------------------------------------
# 5. Backtests (Backtest page)
# ---------------------------------------------------------------------------
log_info "[5/8] Backtests list"
backtest_response=$(curl_body -H "$AUTH_HEADER" "$BASE_URL/api/v1/backtests")
status=$(http_code -H "$AUTH_HEADER" "$BASE_URL/api/v1/backtests")
if [ "$status" = "200" ]; then
  log_pass "/backtests returns 200"
else
  log_fail "/backtests returned HTTP $status"
fi
if echo "$backtest_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'items' in d and 'total' in d else 1)" 2>/dev/null; then
  log_pass "/backtests response shape is valid"
else
  log_fail "/backtests response shape invalid: $backtest_response"
fi

# ---------------------------------------------------------------------------
# 6. Results AI
# ---------------------------------------------------------------------------
log_info "[6/8] Results AI analyze"
ai_response=$(curl_body -X POST "$BASE_URL/api/v1/ai/results-ai/analyze" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "backtest_result": {
      "total_return": 0.15,
      "sharpe_ratio": 1.2,
      "max_drawdown": -0.08,
      "win_rate": 0.55,
      "trades": 100
    },
    "strategy_context": {"name":"Demo Strategy"},
    "question": "What are the main risks?"
  }')

if echo "$ai_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'summary' in d else 1)" 2>/dev/null; then
  log_pass "Results AI analyze returns summary"
else
  log_fail "Results AI analyze failed: $ai_response"
fi

# ---------------------------------------------------------------------------
# 7. Fuzzy Builder generate
# ---------------------------------------------------------------------------
log_info "[7/8] Fuzzy Builder generate"
fuzzy_response=$(curl_body -X POST "$BASE_URL/api/v1/fuzzy/generate" \
  -H "$AUTH_HEADER" \
  -H "Content-Type: application/json" \
  -d '{
    "template": "balanced",
    "name": "Smoke Test Fuzzy Strategy",
    "buy_threshold": 0.62,
    "sell_threshold": 0.58
  }')

if echo "$fuzzy_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'strategy_ir' in d else 1)" 2>/dev/null; then
  log_pass "Fuzzy generate returns strategy_ir"
else
  log_fail "Fuzzy generate failed: $fuzzy_response"
fi

# ---------------------------------------------------------------------------
# 8. Indicator marketplace
# ---------------------------------------------------------------------------
log_info "[8/8] Indicator marketplace"
market_response=$(curl_body -H "$AUTH_HEADER" "$BASE_URL/api/v1/indicator-marketplace")

if echo "$market_response" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'items' in d else 1)" 2>/dev/null; then
  count=$(echo "$market_response" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('items',[])))")
  log_pass "Indicator marketplace returns $count indicators"
else
  log_fail "Indicator marketplace failed: $market_response"
fi

# ---------------------------------------------------------------------------
# 9. Frontend HTML title (bonus check)
# ---------------------------------------------------------------------------
log_info "[Bonus] Frontend HTML title"
frontend_html=$(curl_body -L --max-time "$TIMEOUT" "$FRONTEND_URL" 2>/dev/null || true)
if [ -n "$frontend_html" ] && echo "$frontend_html" | grep -q "<title>.*</title>"; then
  title=$(echo "$frontend_html" | grep -oE "<title>[^<]+</title>" | head -1)
  log_pass "Frontend HTML title found: $title"
else
  log_warn "Frontend HTML title not found (frontend may not be running or title missing)"
fi

login_html_status=$(http_code -L "$FRONTEND_URL/login")
if [ "$login_html_status" = "200" ]; then
  log_pass "SPA /login route returns 200"
else
  log_fail "SPA /login returned HTTP $login_html_status"
fi

openapi_response=$(curl_body "$BASE_URL/openapi.json")
if echo "$openapi_response" | python3 -c "import sys,json; d=json.load(sys.stdin); paths=d.get('paths',{}); needed=['/api/v1/ai/results-ai/analyze','/api/v1/fuzzy/generate','/api/v1/indicator-marketplace']; sys.exit(0 if all(p in paths for p in needed) else 1)" 2>/dev/null; then
  log_pass "OpenAPI includes Results AI, Fuzzy, and Indicator Marketplace"
else
  log_fail "OpenAPI missing expected MVP endpoints"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Smoke Test Summary ==="
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
if [ -n "$WARNINGS" ]; then
  echo -e "${YELLOW}Warnings:${NC}$WARNINGS"
fi

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}All critical checks passed.${NC}"
  exit 0
else
  echo -e "${RED}Some checks failed. Please review the output above.${NC}"
  exit 1
fi
