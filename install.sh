#!/bin/bash
# DealerEye One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash

set -e

echo "=========================================="
echo "  DealerEye Analytics Platform Installer"
echo "=========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    echo "Install: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running or you don't have permissions."
    echo "Try: sudo usermod -aG docker $USER && newgrp docker"
    exit 1
fi

# Check docker compose (v2 syntax: docker compose)
if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Error: Docker Compose is not installed."
    echo "Install: sudo apt-get update && sudo apt-get install docker-compose-plugin"
    exit 1
fi

# Default installation directory
INSTALL_DIR="$HOME/dealereye"

echo "Installing to: $INSTALL_DIR"
echo ""

# Clone or update repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "Cloning DealerEye repository..."
    git clone https://github.com/espressojuice/dealereye.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create .env if needed
if [ ! -f .env ]; then
    echo "Creating .env configuration..."
    cp .env.example .env
    echo "✓ Created .env (you can edit later: nano $INSTALL_DIR/.env)"
fi

# Start Docker services
echo ""
echo "Starting Docker services (PostgreSQL, Redis, MQTT, API)..."
cd "$INSTALL_DIR/deployments/docker"
$DOCKER_COMPOSE up -d

echo ""
echo "Waiting for services to start..."
sleep 15

# Check services
if $DOCKER_COMPOSE ps | grep -q "Up\|running"; then
    echo "✓ Docker services started"
else
    echo "⚠️  Warning: Services may not have started correctly"
    echo "Check logs: cd $INSTALL_DIR/deployments/docker && $DOCKER_COMPOSE logs"
fi

# Initialize database
echo ""
echo "Initializing database..."
cd "$INSTALL_DIR"

# Install Python dependencies quietly
pip3 install --user pydantic sqlalchemy psycopg2-binary passlib -q 2>/dev/null || {
    echo "⚠️  Warning: Could not install Python dependencies"
    echo "Install manually: pip3 install pydantic sqlalchemy psycopg2-binary passlib"
}

python3 deployments/scripts/init_db.py --sample-data 2>/dev/null || {
    echo "⚠️  Warning: Database initialization failed"
    echo "You may need to run manually: python3 $INSTALL_DIR/deployments/scripts/init_db.py --sample-data"
}

echo ""
echo "=========================================="
echo "✅ DealerEye Installed!"
echo "=========================================="
echo ""
echo "Location: $INSTALL_DIR"
echo ""
echo "Services:"
echo "  • API Documentation: http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/health"
echo ""
echo "Next steps:"
echo ""
echo "1. Test the API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "2. View logs:"
echo "   cd $INSTALL_DIR/deployments/docker"
echo "   $DOCKER_COMPOSE logs -f api"
echo ""
echo "3. Install dashboard (optional):"
echo "   cd $INSTALL_DIR/dashboard"
echo "   npm install && npm run dev"
echo ""
echo "4. Stop services:"
echo "   cd $INSTALL_DIR/deployments/docker"
echo "   $DOCKER_COMPOSE down"
echo ""
echo "Documentation: $INSTALL_DIR/QUICKSTART.md"
echo ""
