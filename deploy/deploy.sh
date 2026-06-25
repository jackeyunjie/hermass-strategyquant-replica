#!/bin/bash
# =============================================================================
# Hermass StrategyQuant Replica - Deployment Script
# Target: quant.superalpha.com.cn @ 8.130.125.201
# Usage:
#   ./deploy.sh          # Full first-time setup (requires root)
#   ./deploy.sh --ci     # CI/CD mode: skip system setup, build & restart only
# =============================================================================
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Configuration
APP_DIR="${APP_DIR:-/opt/hermass-strategyquant-replica}"
DOMAIN="quant.superalpha.com.cn"
SETUP_MODE="full"

# Parse arguments
for arg in "$@"; do
  case $arg in
    --ci)
      SETUP_MODE="ci"
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--ci]"
      echo "  --ci    CI/CD mode: skip system setup, build and restart services only"
      exit 0
      ;;
  esac
done

log_info "Hermass Deployment Script"
log_info "Mode: $SETUP_MODE"
log_info "App directory: $APP_DIR"

# -----------------------------------------------------------------------------
# Full setup mode: require root and install system dependencies
# -----------------------------------------------------------------------------
if [ "$SETUP_MODE" = "full" ]; then
  if [[ $EUID -ne 0 ]]; then
     log_error "This script must be run as root for full setup"
     exit 1
  fi

  log_step "Updating system packages..."
  if command -v yum &> /dev/null; then
    yum update -y
    yum install -y docker docker-compose-plugin git
  elif command -v apt-get &> /dev/null; then
    apt-get update
    apt-get install -y docker.io docker-compose-plugin git
  else
    log_error "Unsupported package manager. Please install Docker, Docker Compose, Git manually."
    exit 1
  fi

  log_step "Starting Docker service..."
  systemctl enable docker
  systemctl start docker

  log_step "Creating app directory..."
  mkdir -p "$APP_DIR"
fi

# -----------------------------------------------------------------------------
# Common checks (both modes)
# -----------------------------------------------------------------------------
if ! command -v docker &> /dev/null; then
  log_error "Docker is not installed or not in PATH"
  exit 1
fi

if docker compose version &> /dev/null; then
  COMPOSE_CMD="docker compose"
elif docker-compose --version &> /dev/null; then
  COMPOSE_CMD="docker-compose"
else
  log_error "Docker Compose plugin is not installed"
  exit 1
fi

mkdir -p "$APP_DIR"

# -----------------------------------------------------------------------------
# Environment configuration
# -----------------------------------------------------------------------------
log_step "Checking environment configuration..."

if [ -f "$APP_DIR/.env" ]; then
  log_info ".env already exists, preserving existing configuration"
else
  log_info "Creating new .env file..."
  DB_PASSWORD=$(openssl rand -base64 32)
  SECRET_KEY=$(openssl rand -hex 32)

  cat > "$APP_DIR/.env" <<ENV_EOF
# Database
DATABASE_URL=postgresql+asyncpg://hermass:${DB_PASSWORD}@db:5432/hermass
DB_USER=hermass
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=hermass

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Security
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# App
APP_NAME=Hermass StrategyQuant
DEBUG=false
NGINX_PORT=8081

# CORS
BACKEND_CORS_ORIGINS=https://${DOMAIN}
ENV_EOF

  log_warn "New .env created. Save credentials: DB=${DB_PASSWORD} SECRET=${SECRET_KEY}"
fi

# -----------------------------------------------------------------------------
# Build and start all services via Docker Compose
# -----------------------------------------------------------------------------
log_step "Building and starting services..."
cd "$APP_DIR"

# Copy .env to deploy/ for compose to pick up
cp "$APP_DIR/.env" deploy/.env 2>/dev/null || true

cd deploy
$COMPOSE_CMD pull 2>/dev/null || true
$COMPOSE_CMD up -d --build --remove-orphans

# -----------------------------------------------------------------------------
# Database migrations
# -----------------------------------------------------------------------------
log_step "Running database migrations..."
sleep 10

for i in {1..30}; do
  if $COMPOSE_CMD ps | grep backend | grep -q "healthy"; then
    log_info "Backend is healthy"
    break
  fi
  if [ "$i" -eq 30 ]; then
    log_warn "Backend did not become healthy within 5 minutes, continuing..."
  fi
  sleep 10
done

$COMPOSE_CMD exec -T backend alembic upgrade head || {
  log_warn "Migration command failed. Database may already be up-to-date."
}

# Seed database (full setup only)
if [ "$SETUP_MODE" = "full" ]; then
  $COMPOSE_CMD exec -T backend python scripts/seed_db.py --create-tables || {
    log_warn "Async database seeding failed, retrying sync fallback..."
    $COMPOSE_CMD exec -T backend python scripts/seed_db.py --create-tables --sync || {
      log_warn "Database seeding failed or already seeded."
    }
  }
fi

# -----------------------------------------------------------------------------
# Firewall (full setup only)
# -----------------------------------------------------------------------------
if [ "$SETUP_MODE" = "full" ]; then
  log_step "Configuring firewall..."
  if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-service=http || true
    firewall-cmd --permanent --add-service=https || true
    firewall-cmd --reload || true
  elif command -v ufw &> /dev/null; then
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
  fi

  log_warn "For HTTPS, point a reverse proxy (e.g., Caddy/nginx) at port 80."
  echo ""
  echo "Option A — Caddy (simplest):"
  echo "  caddy reverse-proxy --from ${DOMAIN} --to :80"
  echo ""
  echo "Option B — certbot + nginx on host:"
  echo "  apt install certbot python3-certbot-nginx"
  echo "  certbot --nginx -d ${DOMAIN}"
fi

# -----------------------------------------------------------------------------
# Cleanup
# -----------------------------------------------------------------------------
log_step "Cleaning up unused Docker resources..."
docker system prune -f || true

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
log_info "Deployment complete!"
echo ""
echo "Service URLs:"
echo "  - http://${DOMAIN} (Frontend + API)"
echo "  - http://${DOMAIN}/docs (API Swagger Docs)"
echo "  - http://${DOMAIN}/health (Health Check)"
echo ""
echo "Useful commands:"
echo "  cd ${APP_DIR}/deploy && docker compose logs -f backend"
echo "  cd ${APP_DIR}/deploy && docker compose logs -f worker"
echo "  cd ${APP_DIR}/deploy && docker compose ps"
echo "  cd ${APP_DIR}/deploy && docker compose exec backend bash"
echo ""
if [ "$SETUP_MODE" = "full" ]; then
  echo "Credentials saved in: ${APP_DIR}/.env"
fi
