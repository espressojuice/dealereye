#!/bin/bash
set -euo pipefail

APP_NAME="dealereye"
REPO_URL="https://github.com/espressojuice/dealereye.git"
INSTALL_DIR="/opt/${APP_NAME}"
CONTAINER_NAME="${APP_NAME}"
PORT=8080

echo "== ${APP_NAME} Auto-Installer for Jetson =="

# 1️⃣ Detect Docker or install if missing
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg lsb-release
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io
  sudo systemctl enable docker
  sudo systemctl start docker
  sudo usermod -aG docker $USER
  echo "Docker installed. You may need to log out and back in once."
fi

# 2️⃣ Pull or update repo
if [ ! -d "$INSTALL_DIR" ]; then
  echo "Cloning repository..."
  sudo git clone "$REPO_URL" "$INSTALL_DIR"
else
  echo "Updating repository..."
  cd "$INSTALL_DIR"
  sudo git fetch --all
  sudo git reset --hard origin/main
fi

cd "$INSTALL_DIR"

# 3️⃣ Stop and remove existing container (if running)
if sudo docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "Stopping old container..."
  sudo docker stop "$CONTAINER_NAME" || true
  sudo docker rm "$CONTAINER_NAME" || true
fi

# 4️⃣ Build and run container
echo "Building Docker image..."
sudo docker build -t "$APP_NAME" .

echo "Starting container..."
sudo docker run -d \
  --restart unless-stopped \
  -p ${PORT}:8080 \
  --name "$CONTAINER_NAME" \
  -v ~/.aws:/root/.aws \
  "$APP_NAME"

# 5️⃣ Show status and local URL
echo ""
echo "== Deployment complete =="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

LAN_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "Access the app at: http://${LAN_IP}:${PORT}/"
echo "============================================"
