#!/bin/bash
# Quick start script for DealerEye development environment

set -e

echo "=========================================="
echo "DealerEye Quick Start"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
    echo ""
fi

# Start control plane services
echo "Starting control plane services (PostgreSQL, Redis, MQTT, API)..."
cd deployments/docker
docker-compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 10

# Initialize database
echo ""
echo "Initializing database..."
cd ../..
python3 deployments/scripts/init_db.py --sample-data

echo ""
echo "=========================================="
echo "✅ DealerEye services started!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis: localhost:6379"
echo "  • MQTT Broker: localhost:1883"
echo "  • Control Plane API: http://localhost:8000"
echo ""
echo "API Docs: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health"
echo ""
echo "To start the dashboard:"
echo "  cd dashboard"
echo "  npm install"
echo "  npm run dev"
echo ""
echo "To view logs:"
echo "  cd deployments/docker"
echo "  docker-compose logs -f"
echo ""
echo "To stop services:"
echo "  cd deployments/docker"
echo "  docker-compose down"
echo ""
