#!/bin/bash
# =============================================================================
# Hermass StrategyQuant Replica - First-Time Server Setup
# Run this script ONCE on the server as root before enabling GitHub Actions.
# =============================================================================
set -euo pipefail

APP_DIR="/opt/hermass-strategyquant-replica"
REPO_URL="https://github.com/jackeyunjie/hermass-strategyquant-replica.git"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [[ $EUID -ne 0 ]]; then
  log_error "This script must be run as root"
  exit 1
fi

echo "=== Hermass First-Time Server Setup ==="
echo "Server: $(hostname)"
echo "Date: $(date)"
echo ""

# Install dependencies
log_info "Installing dependencies..."
if command -v yum &> /dev/null; then
  yum update -y
  yum install -y docker docker-compose-plugin git nginx curl openssl
elif command -v apt-get &> /dev/null; then
  apt-get update
  apt-get install -y docker.io docker-compose-plugin git nginx curl openssl
else
  log_error "Unsupported OS. Install Docker, Docker Compose, Git, Nginx manually."
  exit 1
fi

# Start Docker
log_info "Enabling and starting Docker..."
systemctl enable docker
systemctl start docker

# Generate SSH key for GitHub Actions (optional but recommended)
if [ ! -f /root/.ssh/id_rsa ]; then
  log_info "Generating SSH key for GitHub Actions..."
  mkdir -p /root/.ssh
  ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa -N "" -C "github-actions-hermass"
  log_warn "Add the following PUBLIC key to GitHub Secrets as SERVER_SSH_KEY:"
  echo ""
  cat /root/.ssh/id_rsa
  echo ""
  log_warn "Also add the following to /root/.ssh/authorized_keys on this server:"
  cat /root/.ssh/id_rsa.pub
  echo ""
else
  log_warn "SSH key already exists at /root/.ssh/id_rsa"
fi

# Clone repository
log_info "Cloning repository..."
if [ -d "$APP_DIR/.git" ]; then
  log_warn "App directory already exists, skipping clone"
else
  rm -rf "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi

# Run full deployment
log_info "Running full deployment..."
cd "$APP_DIR/deploy"
bash deploy.sh

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Configure DNS A record: quant -> 8.130.125.201"
echo "2. Configure SSL certificate"
echo "3. Add GitHub Secrets and enable GitHub Actions workflow"
