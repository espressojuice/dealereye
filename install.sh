#!/bin/bash
# DealerEye One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash

set -e

echo "=========================================="
echo "  DealerEye Analytics Platform Installer"
echo "=========================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null || ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not installed or not running."
    exit 1
fi

# Ask for installation directory
read -p "Install directory [default: ~/dealereye]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-~/dealereye}
INSTALL_DIR=$(eval echo $INSTALL_DIR)

# Clone repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull origin main
else
    echo "Cloning DealerEye..."
    git clone https://github.com/espressojuice/dealereye.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edit .env with your settings: nano $INSTALL_DIR/.env"
fi

# Start services
echo "Starting Docker services..."
cd deployments/docker
docker-compose up -d

echo "Waiting for services..."
sleep 15

# Initialize database
echo "Initializing database..."
cd ../..
pip3 install --user pydantic sqlalchemy psycopg2-binary passlib -q
python3 deployments/scripts/init_db.py --sample-data

echo ""
echo "✅ DealerEye installed at: $INSTALL_DIR"
echo ""
echo "API: http://localhost:8000/docs"
echo ""
echo "Start dashboard:"
echo "  cd $INSTALL_DIR/dashboard && npm install && npm run dev"
echo ""
