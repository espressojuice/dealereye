#!/bin/bash
# DealerEye One-Line Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash

set -e

echo "=========================================="
echo "  DealerEye Analytics Platform Installer"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root. Consider running as regular user."
    SUDO=""
else
    SUDO="sudo"
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    $SUDO usermod -aG docker $USER
    echo "✓ Docker installed"
    echo "⚠️  You may need to log out and back in for Docker permissions to take effect"
    echo "   Then run this installer again."
    exit 0
fi

if ! docker info > /dev/null 2>&1; then
    echo "Docker is installed but you don't have permissions."
    echo "Adding you to docker group..."
    $SUDO usermod -aG docker $USER
    echo "✓ Added to docker group"
    echo "⚠️  Please log out and back in, then run this installer again:"
    echo "   curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash"
    exit 0
fi

# Check and install Docker Compose
DOCKER_COMPOSE=""
if docker compose version > /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
    echo "✓ Docker Compose v2 detected"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
    echo "✓ Docker Compose v1 detected"
else
    echo "Docker Compose not found. Installing..."
    
    # Detect OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        OS=$(uname -s)
    fi
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        echo "Installing Docker Compose plugin for Ubuntu/Debian..."
        $SUDO apt-get update -qq
        $SUDO apt-get install -y docker-compose-plugin
        DOCKER_COMPOSE="docker compose"
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "fedora" ]]; then
        echo "Installing Docker Compose plugin for RHEL/CentOS/Fedora..."
        $SUDO yum install -y docker-compose-plugin
        DOCKER_COMPOSE="docker compose"
    else
        # Fallback to standalone docker-compose
        echo "Installing standalone docker-compose..."
        $SUDO curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        $SUDO chmod +x /usr/local/bin/docker-compose
        DOCKER_COMPOSE="docker-compose"
    fi
    
    echo "✓ Docker Compose installed"
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "Python 3 not found. Installing..."
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        $SUDO apt-get install -y python3 python3-pip
    else
        echo "Please install Python 3 manually and run this script again."
        exit 1
    fi
fi

# Check git
if ! command -v git &> /dev/null; then
    echo "Git not found. Installing..."
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        $SUDO apt-get install -y git
    else
        echo "Please install git manually and run this script again."
        exit 1
    fi
fi

echo "✓ All prerequisites installed"
echo ""

# Installation directory
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
    echo "✓ Created .env (edit later: nano $INSTALL_DIR/.env)"
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

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user pydantic sqlalchemy psycopg2-binary passlib -q 2>/dev/null || {
    echo "⚠️  Warning: Could not install Python dependencies via pip"
    echo "Trying with apt..."
    $SUDO apt-get install -y python3-pydantic python3-sqlalchemy python3-psycopg2 2>/dev/null || true
}

python3 deployments/scripts/init_db.py --sample-data 2>/dev/null || {
    echo "⚠️  Database initialization will be attempted when you first run the API"
}

echo ""
echo "=========================================="
echo "✅ DealerEye Installed Successfully!"
echo "=========================================="
echo ""
echo "Location: $INSTALL_DIR"
echo ""
echo "Services Running:"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis: localhost:6379"
echo "  • MQTT Broker: localhost:1883"
echo "  • API: http://localhost:8000"
echo ""
echo "Quick Start:"
echo ""
echo "1. Check API health:"
echo "   curl http://localhost:8000/health"
echo ""
echo "2. View API documentation:"
echo "   Open http://localhost:8000/docs in your browser"
echo ""
echo "3. View logs:"
echo "   cd $INSTALL_DIR/deployments/docker"
echo "   $DOCKER_COMPOSE logs -f api"
echo ""
echo "4. Install dashboard (optional):"
echo "   cd $INSTALL_DIR/dashboard"
echo "   npm install && npm run dev"
echo "   # Dashboard at http://localhost:3000"
echo ""
echo "5. Stop services:"
echo "   cd $INSTALL_DIR/deployments/docker"
echo "   $DOCKER_COMPOSE down"
echo ""
echo "Documentation:"
echo "  • Quick Start: $INSTALL_DIR/QUICKSTART.md"
echo "  • README: $INSTALL_DIR/README-NEW.md"
echo ""
echo "Sample Credentials:"
echo "  Email: admin@texarkanauto.com"
echo "  Password: changeme123"
echo ""
echo "🎉 Ready to go! Happy Analytics!"
echo ""
