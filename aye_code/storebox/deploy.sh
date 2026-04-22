#!/bin/sh
# AYY-27 — Deploy script: bring up the full store box
#
# Usage:
#   ./deploy.sh                    # Deploy with defaults
#   STORE_ID=store-0042 ./deploy.sh  # Deploy with specific store ID
#   ./deploy.sh --rebuild          # Rebuild Docker images first
#
# Prerequisites: Docker + Docker Compose installed

set -eu

cd "$(dirname "$0")/.."

STORE_ID="${STORE_ID:-store-0001}"
echo "=== AYY-27 Store Box Deploy ==="
echo "Store ID: $STORE_ID"

# Generate self-signed cert if not present
CERTS_DIR="storebox/certs"
if [ ! -f "$CERTS_DIR/selfsigned.crt" ] || [ ! -f "$CERTS_DIR/selfsigned.key" ]; then
    echo "Generating self-signed certificate..."
    mkdir -p "$CERTS_DIR"
    openssl req -x509 -newkey rsa:2048 -keyout "$CERTS_DIR/selfsigned.key" \
        -out "$CERTS_DIR/selfsigned.crt" -days 365 -nodes \
        -subj "/C=IN/ST=Karnataka/L=Bengaluru/O=Ayyyanar Tech/OU=Store Box/CN=$STORE_ID"
    echo "  Certificate generated."
fi

# Create data directory
mkdir -p storebox/data/media

# Build and start
if [ "${1:-}" = "--rebuild" ]; then
    echo "Rebuilding images..."
    docker compose -f storebox/docker-compose.yml build --no-cache
else
    echo "Using cached images (add --rebuild to force rebuild)"
    docker compose -f storebox/docker-compose.yml build
fi

echo ""
echo "Starting services..."
docker compose -f storebox/docker-compose.yml up -d

echo ""
echo "Waiting for health checks..."
sleep 5

# Check all services are up
if docker compose -f storebox/docker-compose.yml ps | grep -q "unhealthy"; then
    echo "WARNING: One or more services are unhealthy. Check logs:"
    echo "  docker compose -f storebox/docker-compose.yml logs"
else
    echo "All services healthy."
fi

echo ""
echo "Store box available at:"
echo "  HTTP:  http://localhost:${NGINX_HTTP_PORT:-80}"
echo "  HTTPS: https://localhost:${NGINX_HTTPS_PORT:-443}"
echo ""
echo "Django admin:  https://localhost/admin/"
echo "Till POS:      https://localhost/till/"
echo "API:           https://localhost/api/"
echo ""
echo "Run 'docker compose -f storebox/docker-compose.yml logs -f' to follow logs."
