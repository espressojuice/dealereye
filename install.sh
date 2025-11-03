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

# Create config directory for persistent camera settings
sudo mkdir -p "${INSTALL_DIR}/config"

# Mount TensorRT engine if it exists (for persistence across rebuilds)
TENSORRT_MOUNT=""
if [ -f "${INSTALL_DIR}/yolov8n.engine" ]; then
  TENSORRT_MOUNT="-v ${INSTALL_DIR}/yolov8n.engine:/app/yolov8n.engine"
  echo "Found existing TensorRT engine, mounting it..."
fi

# Performance tuning via environment variables (optional)
# DETECTION_INTERVAL: Run AI detection every N frames (default: 5, higher=faster but fewer detections)
# INFERENCE_WIDTH: Resize frames for AI to this width (default: 0=full res, 640 recommended for 2-3x speedup)
PERF_ENV=""
if [ ! -z "${DETECTION_INTERVAL:-}" ]; then
  PERF_ENV="${PERF_ENV} -e DETECTION_INTERVAL=${DETECTION_INTERVAL}"
fi
if [ ! -z "${INFERENCE_WIDTH:-}" ]; then
  PERF_ENV="${PERF_ENV} -e INFERENCE_WIDTH=${INFERENCE_WIDTH}"
fi

# Build device mount arguments (only if devices exist)
DEVICE_MOUNTS=""
for dev in nvhost-ctrl nvhost-ctrl-gpu nvhost-prof-gpu nvmap nvhost-gpu nvhost-as-gpu; do
  if [ -e "/dev/$dev" ]; then
    DEVICE_MOUNTS="${DEVICE_MOUNTS} --device /dev/$dev"
  fi
done

# Build library mount arguments (only if paths exist)
LIB_MOUNTS=""
if [ -d "/usr/lib/aarch64-linux-gnu/tegra" ]; then
  LIB_MOUNTS="${LIB_MOUNTS} -v /usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu/tegra:ro"
fi
if [ -d "/usr/lib/aarch64-linux-gnu/tegra-egl" ]; then
  LIB_MOUNTS="${LIB_MOUNTS} -v /usr/lib/aarch64-linux-gnu/tegra-egl:/usr/lib/aarch64-linux-gnu/tegra-egl:ro"
fi

sudo docker run -d \
  --restart unless-stopped \
  --runtime nvidia \
  --gpus all \
  ${DEVICE_MOUNTS} \
  ${LIB_MOUNTS} \
  -p ${PORT}:8080 \
  --name "$CONTAINER_NAME" \
  -v ~/.aws:/root/.aws \
  -v "${INSTALL_DIR}/config:/app/config" \
  -v /usr/bin/docker:/usr/bin/docker \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/bin/curl:/usr/bin/curl \
  -v /usr/bin/bash:/usr/bin/bash \
  ${TENSORRT_MOUNT} \
  ${PERF_ENV} \
  "$APP_NAME"

# 5️⃣ TensorRT Optimization (if not already done)
if [ ! -f "${INSTALL_DIR}/yolov8n.engine" ]; then
  echo ""
  echo "🚀 Optimizing YOLOv8 model with TensorRT (this may take 5-10 minutes)..."
  echo "This is a one-time optimization that will speed up AI inference by 3-5x"

  # Wait for container to be ready
  sleep 5

  # Run optimization inside container
  sudo docker exec "$CONTAINER_NAME" python3 /app/optimize_model.py \
    --model yolov8n.pt \
    --half \
    --benchmark 2>&1 | grep -E "Building|Saved|Performance|FPS" || true

  # Copy the optimized engine to host for persistence
  sudo docker cp "${CONTAINER_NAME}:/app/yolov8n.engine" "${INSTALL_DIR}/yolov8n.engine" 2>/dev/null || true

  # Restart container to pick up TensorRT engine
  echo "Restarting container with TensorRT engine..."
  sudo docker restart "$CONTAINER_NAME"
  sleep 3

  echo "✅ TensorRT optimization complete!"
else
  echo ""
  echo "✅ TensorRT engine already exists, skipping optimization"
fi

# 6️⃣ Show status and local URL
echo ""
echo "== Deployment complete =="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

LAN_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "Access the dashboard at: http://${LAN_IP}:${PORT}/dashboard"
echo "============================================"
