#!/bin/bash
#
# Run all tests: backend, frontend unit tests, and E2E tests
#
# This script can either:
# 1. Spin up a dedicated test Docker stack (default)
# 2. Use an existing running stack (--use-existing)
#
# Usage:
#   ./run-tests.sh                     # Run all tests with dedicated stack
#   ./run-tests.sh --use-existing 9800 # Run tests against existing stack on port 9800
#   ./run-tests.sh --backend           # Run only backend tests
#   ./run-tests.sh --frontend          # Run only frontend unit tests
#   ./run-tests.sh --e2e               # Run only E2E tests
#   ./run-tests.sh --keep              # Keep test stack running after tests
#   ./run-tests.sh --no-build          # Skip Docker image builds
#
# Examples:
#   ./run-tests.sh                           # Full test suite with isolated stack
#   ./run-tests.sh --use-existing 9800       # Quick run against dev stack
#   ./run-tests.sh --backend --frontend      # Skip E2E tests
#   ./run-tests.sh --e2e --headed            # E2E only in headed mode
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Configuration defaults
TEST_PORT=9900
PROJECT_NAME="ws-tests"
USE_EXISTING=0
KEEP_STACK=0
NO_BUILD=0
HEADED=0

# Test selection (default: all)
RUN_BACKEND=0
RUN_FRONTEND=0
RUN_E2E=0
RUN_ALL=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_header() { echo -e "\n${BOLD}${CYAN}════════════════════════════════════════${NC}"; echo -e "${BOLD}${CYAN}  $1${NC}"; echo -e "${BOLD}${CYAN}════════════════════════════════════════${NC}\n"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-existing)
            USE_EXISTING=1
            if [[ -n "$2" && ! "$2" =~ ^-- ]]; then
                TEST_PORT="$2"
                shift
            fi
            shift
            ;;
        --keep)
            KEEP_STACK=1
            shift
            ;;
        --no-build)
            NO_BUILD=1
            shift
            ;;
        --headed)
            HEADED=1
            shift
            ;;
        --backend|-b)
            RUN_BACKEND=1
            RUN_ALL=0
            shift
            ;;
        --frontend|-f)
            RUN_FRONTEND=1
            RUN_ALL=0
            shift
            ;;
        --e2e|-e)
            RUN_E2E=1
            RUN_ALL=0
            shift
            ;;
        --port|-p)
            TEST_PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --use-existing [PORT]  Use existing Docker stack (default port: 9800)"
            echo "  --port, -p PORT        Port for test stack (default: 9900)"
            echo "  --keep                 Keep test stack running after tests"
            echo "  --no-build             Skip Docker image builds"
            echo "  --headed               Run E2E tests in headed mode"
            echo "  --backend, -b          Run only backend tests"
            echo "  --frontend, -f         Run only frontend unit tests"
            echo "  --e2e, -e              Run only E2E tests"
            echo "  --help, -h             Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Full test suite"
            echo "  $0 --use-existing 9800       # Use existing dev stack"
            echo "  $0 --backend --frontend      # Skip E2E tests"
            echo "  $0 --e2e --headed            # E2E only in headed mode"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# If run all, enable all test types
if [ "$RUN_ALL" -eq 1 ]; then
    RUN_BACKEND=1
    RUN_FRONTEND=1
    RUN_E2E=1
fi

# Results tracking
BACKEND_RESULT=0
FRONTEND_RESULT=0
E2E_RESULT=0
OVERALL_RESULT=0

# Compute container name based on project
get_web_container() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        # Find the running container matching the port
        docker ps --format '{{.Names}}' | grep -E "ws-web" | head -1
    else
        echo "${PROJECT_NAME}-ws-web-1"
    fi
}

# Create test environment file and compose override
create_test_env() {
    local env_file="$BACKEND_DIR/.env-tests"
    local compose_override="$BACKEND_DIR/docker-compose.tests.yaml"

    log_info "Creating test environment file..."
    cat > "$env_file" << EOF
WS_SECRET_KEY=test_secret_key_$(date +%s)
WS_DB_USER=test
WS_DB_PASSWORD=test_pw
WS_DB_NAME=testdb

WS_WEB_EXTERNAL_PORT=$TEST_PORT
WS_WEB_INTERNAL_PORT=$TEST_PORT

WS_FRONTEND_URL=http://localhost:5173
WS_ALLOWED_HOSTS=localhost,127.0.0.1

WS_ASK_FEATURE_ENABLED=false
WS_BRAND_NAME=Hyperclast-Tests
WS_LANDING_TEMPLATE=core/landing.html
WS_DEV_SIDEBAR_ENABLED=false
EOF
    log_success "Created $env_file"

    log_info "Creating compose override for tests..."
    cat > "$compose_override" << 'EOF'
# Override env_file to use .env-tests instead of .env-docker
services:
  ws-db:
    env_file:
      - .env-tests
  ws-web:
    env_file:
      - .env-tests
  ws-rq:
    env_file:
      - .env-tests
EOF
    log_success "Created $compose_override"
}

# Check if port is available
check_port() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        return 0
    fi

    log_info "Checking if port $TEST_PORT is available..."
    if lsof -i :$TEST_PORT >/dev/null 2>&1; then
        log_error "Port $TEST_PORT is already in use!"
        lsof -i :$TEST_PORT
        exit 1
    fi
    log_success "Port $TEST_PORT is available"
}

# Start test Docker stack
start_stack() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        log_info "Using existing Docker stack on port $TEST_PORT"
        return 0
    fi

    log_info "Starting test Docker stack on port $TEST_PORT..."
    cd "$BACKEND_DIR"

    # Clean up any stale containers
    docker compose -f docker-compose.yaml -f docker-compose.e2e.yaml -f docker-compose.tests.yaml \
        -p "$PROJECT_NAME" \
        --env-file .env-tests \
        down --remove-orphans 2>/dev/null || true

    local build_flag=""
    if [ "$NO_BUILD" -eq 0 ]; then
        build_flag="--build"
    fi

    docker compose -f docker-compose.yaml -f docker-compose.e2e.yaml -f docker-compose.tests.yaml \
        -p "$PROJECT_NAME" \
        --env-file .env-tests \
        up -d $build_flag

    log_success "Test stack started"
}

# Wait for services to be healthy
wait_for_health() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        return 0
    fi

    log_info "Waiting for services to be healthy..."
    local max_wait=120
    local waited=0

    while [ $waited -lt $max_wait ]; do
        if curl -fsS "http://localhost:$TEST_PORT/" >/dev/null 2>&1; then
            log_success "Services are healthy!"
            return 0
        fi
        echo -n "."
        sleep 2
        waited=$((waited + 2))
    done

    echo ""
    log_error "Services did not become healthy within ${max_wait}s"
    cd "$BACKEND_DIR"
    docker compose -f docker-compose.yaml -f docker-compose.e2e.yaml -f docker-compose.tests.yaml \
        -p "$PROJECT_NAME" \
        --env-file .env-tests \
        logs --tail=50
    return 1
}

# Run migrations
run_migrations() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        return 0
    fi

    log_info "Running database migrations..."
    local container=$(get_web_container)
    docker exec "$container" python manage.py migrate --noinput
    log_success "Migrations complete"
}

# Cleanup function
cleanup() {
    if [ "$USE_EXISTING" -eq 1 ]; then
        return 0
    fi

    if [ "$KEEP_STACK" -eq 1 ]; then
        log_info "Keeping test stack running"
        log_info "Stop with: docker compose -p $PROJECT_NAME down -v"
        return 0
    fi

    log_info "Cleaning up test stack..."
    cd "$BACKEND_DIR"
    docker compose -f docker-compose.yaml -f docker-compose.e2e.yaml -f docker-compose.tests.yaml \
        -p "$PROJECT_NAME" \
        --env-file .env-tests \
        down -v --remove-orphans 2>/dev/null || true

    # Clean up generated files
    rm -f "$BACKEND_DIR/docker-compose.tests.yaml" "$BACKEND_DIR/.env-tests"
    log_success "Test stack cleaned up"
}

# Run backend tests
run_backend_tests() {
    log_header "Backend Tests (Django)"

    local container=$(get_web_container)
    log_info "Running tests in container: $container"
    log_info "Command: python manage.py test --parallel"

    if docker exec "$container" python manage.py test --parallel; then
        log_success "Backend tests passed!"
        return 0
    else
        log_error "Backend tests failed!"
        return 1
    fi
}

# Run frontend unit tests
run_frontend_tests() {
    log_header "Frontend Unit Tests (Vitest)"

    cd "$FRONTEND_DIR"
    log_info "Command: npm test -- --run"

    if npm test -- --run; then
        log_success "Frontend unit tests passed!"
        return 0
    else
        log_error "Frontend unit tests failed!"
        return 1
    fi
}

# Run E2E tests
run_e2e_tests() {
    log_header "E2E Tests (Playwright)"

    cd "$FRONTEND_DIR"

    local cmd="npx playwright test"
    if [ "$HEADED" -eq 1 ]; then
        cmd="$cmd --headed"
    fi

    export TEST_BASE_URL="http://localhost:$TEST_PORT"
    log_info "Base URL: $TEST_BASE_URL"
    log_info "Command: $cmd"

    if $cmd; then
        log_success "E2E tests passed!"
        return 0
    else
        log_error "E2E tests failed!"
        return 1
    fi
}

# Print summary
print_summary() {
    log_header "Test Results Summary"

    local total=0
    local passed=0
    local failed=0

    if [ "$RUN_BACKEND" -eq 1 ]; then
        total=$((total + 1))
        if [ "$BACKEND_RESULT" -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} Backend tests"
            passed=$((passed + 1))
        else
            echo -e "  ${RED}✗${NC} Backend tests"
            failed=$((failed + 1))
        fi
    fi

    if [ "$RUN_FRONTEND" -eq 1 ]; then
        total=$((total + 1))
        if [ "$FRONTEND_RESULT" -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} Frontend unit tests"
            passed=$((passed + 1))
        else
            echo -e "  ${RED}✗${NC} Frontend unit tests"
            failed=$((failed + 1))
        fi
    fi

    if [ "$RUN_E2E" -eq 1 ]; then
        total=$((total + 1))
        if [ "$E2E_RESULT" -eq 0 ]; then
            echo -e "  ${GREEN}✓${NC} E2E tests"
            passed=$((passed + 1))
        else
            echo -e "  ${RED}✗${NC} E2E tests"
            failed=$((failed + 1))
        fi
    fi

    echo ""
    if [ "$failed" -eq 0 ]; then
        echo -e "${GREEN}${BOLD}All $total test suite(s) passed!${NC}"
    else
        echo -e "${RED}${BOLD}$failed of $total test suite(s) failed${NC}"
    fi
    echo ""
}

# Main execution
main() {
    log_header "Test Runner"

    echo "Configuration:"
    echo "  Port: $TEST_PORT"
    echo "  Use existing stack: $USE_EXISTING"
    echo "  Keep stack: $KEEP_STACK"
    echo "  Backend tests: $RUN_BACKEND"
    echo "  Frontend tests: $RUN_FRONTEND"
    echo "  E2E tests: $RUN_E2E"
    echo ""

    # Setup
    if [ "$USE_EXISTING" -eq 0 ]; then
        create_test_env
        check_port
    fi

    # Set up cleanup trap
    trap cleanup EXIT

    # Start stack if needed
    start_stack

    # Wait for services
    if ! wait_for_health; then
        exit 1
    fi

    # Run migrations
    run_migrations

    # Run tests in parallel where possible
    # Backend and frontend unit tests can run in parallel
    # E2E tests need to run after as they use the browser

    if [ "$RUN_BACKEND" -eq 1 ] && [ "$RUN_FRONTEND" -eq 1 ]; then
        # Run backend and frontend in parallel
        log_info "Running backend and frontend tests in parallel..."

        # Start backend tests in background
        (run_backend_tests; echo $? > /tmp/backend_result_$$) &
        BACKEND_PID=$!

        # Start frontend tests in background
        (run_frontend_tests; echo $? > /tmp/frontend_result_$$) &
        FRONTEND_PID=$!

        # Wait for both
        wait $BACKEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true

        # Get results
        BACKEND_RESULT=$(cat /tmp/backend_result_$$ 2>/dev/null || echo 1)
        FRONTEND_RESULT=$(cat /tmp/frontend_result_$$ 2>/dev/null || echo 1)
        rm -f /tmp/backend_result_$$ /tmp/frontend_result_$$

    else
        # Run sequentially
        if [ "$RUN_BACKEND" -eq 1 ]; then
            run_backend_tests || BACKEND_RESULT=1
        fi

        if [ "$RUN_FRONTEND" -eq 1 ]; then
            run_frontend_tests || FRONTEND_RESULT=1
        fi
    fi

    # E2E tests run sequentially (browser-based)
    if [ "$RUN_E2E" -eq 1 ]; then
        run_e2e_tests || E2E_RESULT=1
    fi

    # Calculate overall result
    if [ "$BACKEND_RESULT" -ne 0 ] || [ "$FRONTEND_RESULT" -ne 0 ] || [ "$E2E_RESULT" -ne 0 ]; then
        OVERALL_RESULT=1
    fi

    # Print summary
    print_summary

    exit $OVERALL_RESULT
}

main
