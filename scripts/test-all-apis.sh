#!/bin/bash

# Git Review Assistant - Comprehensive API Testing Script
# Tests all backend endpoints and validates responses

# Don't exit on error - we want to test all endpoints
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test result arrays
declare -a PASSED_ENDPOINTS
declare -a FAILED_ENDPOINTS

# Utility functions
log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
    ((TOTAL_TESTS++))
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((PASSED_TESTS++))
    PASSED_ENDPOINTS+=("$1")
}

log_failure() {
    echo -e "${RED}[✗]${NC} $1"
    ((FAILED_TESTS++))
    FAILED_ENDPOINTS+=("$1")
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check if backend is running
check_backend() {
    echo -e "${BLUE}Checking backend availability...${NC}"
    if curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/health" | grep -q "200"; then
        echo -e "${GREEN}Backend is running at ${BACKEND_URL}${NC}"
        return 0
    else
        echo -e "${RED}Backend is not available at ${BACKEND_URL}${NC}"
        echo "Please start the backend with: cd backend && source .venv/bin/activate && uvicorn main:app --reload"
        exit 1
    fi
}

# Test health endpoints
test_health_endpoints() {
    echo -e "\n${BLUE}=== Testing Health & Monitoring Endpoints ===${NC}\n"

    log_test "GET /health"
    if curl -s "${BACKEND_URL}/health" | jq -e '.status == "healthy"' > /dev/null; then
        log_success "GET /health"
    else
        log_failure "GET /health"
    fi

    log_test "GET /health/detailed"
    if curl -s "${BACKEND_URL}/health/detailed" | jq -e '.checks.database.status == "healthy"' > /dev/null; then
        log_success "GET /health/detailed"
    else
        log_failure "GET /health/detailed"
    fi

    log_test "GET /metrics"
    if curl -s "${BACKEND_URL}/metrics" | jq -e 'has("requests_total")' > /dev/null; then
        log_success "GET /metrics"
    else
        log_failure "GET /metrics"
    fi

    log_test "GET /status"
    if curl -s "${BACKEND_URL}/status" | jq -e '.status == "operational"' > /dev/null; then
        log_success "GET /status"
    else
        log_failure "GET /status"
    fi
}

# Test review endpoints
test_review_endpoints() {
    echo -e "\n${BLUE}=== Testing Review Endpoints ===${NC}\n"

    # Test manual review
    log_test "POST /review/manual"
    MANUAL_REVIEW=$(curl -s -X POST "${BACKEND_URL}/review/manual" \
        -H "Content-Type: application/json" \
        -d '{"code": "def hello():\n    return \"Hello World\"", "language": "python"}')

    if echo "$MANUAL_REVIEW" | jq -e '.review_id' > /dev/null; then
        REVIEW_ID=$(echo "$MANUAL_REVIEW" | jq -r '.review_id')
        log_success "POST /review/manual (ID: ${REVIEW_ID:0:8}...)"

        # Test fetching the review
        sleep 1
        log_test "GET /review/{review_id}"
        if curl -s "${BACKEND_URL}/review/${REVIEW_ID}" | jq -e '.review.id' > /dev/null; then
            log_success "GET /review/{review_id}"
        else
            log_failure "GET /review/{review_id}"
        fi
    else
        log_failure "POST /review/manual"
    fi

    # Test file review
    log_test "POST /review/files"
    FILES_REVIEW=$(curl -s -X POST "${BACKEND_URL}/review/files" \
        -H "Content-Type: application/json" \
        -d '{"files": [{"filename": "test.py", "content": "def add(a, b):\n    return a + b"}]}')

    if echo "$FILES_REVIEW" | jq -e '.review_id' > /dev/null; then
        log_success "POST /review/files"
    else
        log_failure "POST /review/files"
    fi

    # Test PR review
    log_test "POST /review/pr"
    PR_REVIEW=$(curl -s -X POST "${BACKEND_URL}/review/pr" \
        -H "Content-Type: application/json" \
        -d '{"repository": "facebook/react", "pr_number": 1, "force_refresh": false}')

    if echo "$PR_REVIEW" | jq -e '.review_id' > /dev/null; then
        log_success "POST /review/pr"
    else
        log_failure "POST /review/pr"
    fi

    # Test code review with persistence
    log_test "POST /review/code"
    CODE_REVIEW=$(curl -s -X POST "${BACKEND_URL}/review/code" \
        -H "Content-Type: application/json" \
        -d '{"files": [{"path": "test.js", "content": "console.log(\"test\");"}], "user_id": "test-user", "repository": "test-repo"}')

    if echo "$CODE_REVIEW" | jq -e '.review_id' > /dev/null; then
        log_success "POST /review/code"
    else
        log_failure "POST /review/code"
    fi

    # Test review listing
    log_test "GET /review/"
    if curl -s "${BACKEND_URL}/review/?page=1&per_page=5" | jq -e '.reviews' > /dev/null; then
        log_success "GET /review/ (listing)"
    else
        log_failure "GET /review/ (listing)"
    fi
}

# Test statistics endpoints
test_statistics_endpoints() {
    echo -e "\n${BLUE}=== Testing Statistics & Metrics Endpoints ===${NC}\n"

    log_test "GET /review/stats/overview"
    if curl -s "${BACKEND_URL}/review/stats/overview?days=30" | jq -e '.total_reviews' > /dev/null; then
        log_success "GET /review/stats/overview"
    else
        log_failure "GET /review/stats/overview"
    fi

    log_test "GET /review/history"
    if curl -s "${BACKEND_URL}/review/history?days=7" | jq -e '.reviews' > /dev/null; then
        log_success "GET /review/history"
    else
        log_failure "GET /review/history"
    fi

    log_test "GET /review/stats/user"
    if curl -s "${BACKEND_URL}/review/stats/user?user_id=test-user&days=30" | jq -e '.total_reviews' > /dev/null; then
        log_success "GET /review/stats/user"
    else
        log_failure "GET /review/stats/user"
    fi

    log_test "GET /review/queue/status"
    if curl -s "${BACKEND_URL}/review/queue/status" | jq -e '.pending' > /dev/null; then
        log_success "GET /review/queue/status"
    else
        log_failure "GET /review/queue/status"
    fi

    log_test "GET /review/metrics/user/{user_id}"
    if curl -s "${BACKEND_URL}/review/metrics/user/test-user?days=30" | jq -e '.user_id' > /dev/null; then
        log_success "GET /review/metrics/user/{user_id}"
    else
        log_failure "GET /review/metrics/user/{user_id}"
    fi

    log_test "GET /review/metrics/repository"
    if curl -s "${BACKEND_URL}/review/metrics/repository?repository=test-repo&days=30" | jq -e '.repository' > /dev/null; then
        log_success "GET /review/metrics/repository"
    else
        log_failure "GET /review/metrics/repository"
    fi

    log_test "GET /review/metrics/trending"
    if curl -s "${BACKEND_URL}/review/metrics/trending?days=7&limit=10" | jq -e '.trending_issues' > /dev/null; then
        log_success "GET /review/metrics/trending"
    else
        log_failure "GET /review/metrics/trending"
    fi
}

# Test authentication endpoints
test_auth_endpoints() {
    echo -e "\n${BLUE}=== Testing Authentication Endpoints ===${NC}\n"

    log_test "GET /auth/me (unauthenticated)"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/auth/me")
    if [ "$HTTP_CODE" == "401" ]; then
        log_success "GET /auth/me returns 401 when unauthenticated"
    else
        log_failure "GET /auth/me (expected 401, got $HTTP_CODE)"
    fi

    log_warning "GitHub OAuth endpoints require valid GitHub App credentials"
    log_warning "Skipping POST /auth/github and POST /auth/logout (require auth session)"
}

# Test webhook endpoints
test_webhook_endpoints() {
    echo -e "\n${BLUE}=== Testing Webhook Endpoints ===${NC}\n"

    log_test "GET /webhook/github/health"
    if curl -s "${BACKEND_URL}/webhook/github/health" | jq -e '.status == "healthy"' > /dev/null; then
        log_success "GET /webhook/github/health"
    else
        log_failure "GET /webhook/github/health"
    fi

    if [ "${DEBUG:-false}" == "true" ]; then
        log_test "POST /webhook/github/test (debug mode)"
        TEST_WEBHOOK=$(curl -s -X POST "${BACKEND_URL}/webhook/github/test" \
            -H "Content-Type: application/json" \
            -d '{"action": "opened", "pull_request": {"number": 1, "title": "Test PR"}}')

        if echo "$TEST_WEBHOOK" | jq -e '.message' > /dev/null; then
            log_success "POST /webhook/github/test"
        else
            log_failure "POST /webhook/github/test"
        fi
    else
        log_warning "Skipping webhook test endpoint (requires DEBUG=true)"
    fi
}

# Test frontend API routes
test_frontend_apis() {
    echo -e "\n${BLUE}=== Testing Frontend API Routes ===${NC}\n"

    # Check if frontend is running
    if ! curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}" | grep -q "200\|404"; then
        log_warning "Frontend not running at ${FRONTEND_URL}, skipping frontend tests"
        return
    fi

    log_test "GET /api/health (frontend)"
    if curl -s "${FRONTEND_URL}/api/health" | jq -e '.status == "ok"' > /dev/null; then
        log_success "GET /api/health (frontend)"
    else
        log_failure "GET /api/health (frontend)"
    fi
}

# Performance testing
test_performance() {
    echo -e "\n${BLUE}=== Performance Testing ===${NC}\n"

    log_test "Response time for /health"
    RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" "${BACKEND_URL}/health")
    if (( $(echo "$RESPONSE_TIME < 0.5" | bc -l) )); then
        log_success "GET /health response time: ${RESPONSE_TIME}s (< 0.5s)"
    else
        log_warning "GET /health response time: ${RESPONSE_TIME}s (> 0.5s)"
    fi

    log_test "Response time for /review/manual"
    START_TIME=$(date +%s%N)
    curl -s -X POST "${BACKEND_URL}/review/manual" \
        -H "Content-Type: application/json" \
        -d '{"code": "print(\"test\")", "language": "python"}' > /dev/null
    END_TIME=$(date +%s%N)
    RESPONSE_TIME=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc)

    if (( $(echo "$RESPONSE_TIME < 2" | bc -l) )); then
        log_success "POST /review/manual response time: ${RESPONSE_TIME}s (< 2s)"
    else
        log_warning "POST /review/manual response time: ${RESPONSE_TIME}s (> 2s)"
    fi
}

# Generate test report
generate_report() {
    echo -e "\n${BLUE}=== Test Summary ===${NC}\n"

    PASS_RATE=$(echo "scale=2; ($PASSED_TESTS * 100) / $TOTAL_TESTS" | bc)

    echo "Total Tests: $TOTAL_TESTS"
    echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
    echo -e "Pass Rate: ${PASS_RATE}%"

    if [ ${#FAILED_ENDPOINTS[@]} -gt 0 ]; then
        echo -e "\n${RED}Failed Endpoints:${NC}"
        for endpoint in "${FAILED_ENDPOINTS[@]}"; do
            echo "  - $endpoint"
        done
    fi

    # Save report to file
    REPORT_FILE="api-test-report-$(date +%Y%m%d-%H%M%S).md"
    {
        echo "# API Test Report"
        echo "Date: $(date)"
        echo ""
        echo "## Summary"
        echo "- Total Tests: $TOTAL_TESTS"
        echo "- Passed: $PASSED_TESTS"
        echo "- Failed: $FAILED_TESTS"
        echo "- Pass Rate: ${PASS_RATE}%"
        echo ""
        echo "## Passed Endpoints"
        for endpoint in "${PASSED_ENDPOINTS[@]}"; do
            echo "- ✓ $endpoint"
        done
        echo ""
        if [ ${#FAILED_ENDPOINTS[@]} -gt 0 ]; then
            echo "## Failed Endpoints"
            for endpoint in "${FAILED_ENDPOINTS[@]}"; do
                echo "- ✗ $endpoint"
            done
        fi
    } > "$REPORT_FILE"

    echo -e "\n${GREEN}Report saved to: $REPORT_FILE${NC}"

    # Exit with appropriate code
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}Git Review Assistant - API Testing Suite${NC}"
    echo "=========================================="

    # Check dependencies
    if ! command -v jq &> /dev/null; then
        echo -e "${RED}Error: jq is required but not installed${NC}"
        echo "Install with: brew install jq (macOS) or apt-get install jq (Linux)"
        exit 1
    fi

    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl is required but not installed${NC}"
        exit 1
    fi

    # Run tests
    check_backend
    test_health_endpoints
    test_review_endpoints
    test_statistics_endpoints
    test_auth_endpoints
    test_webhook_endpoints
    test_frontend_apis
    test_performance

    # Generate report
    generate_report
}

# Run main function
main "$@"