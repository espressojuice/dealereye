#!/bin/bash
# Auto-update script - runs from inside container to update itself
set -e

APP_NAME="dealereye"
INSTALL_DIR="/opt/${APP_NAME}"
CONTAINER_NAME="${APP_NAME}"

echo "[Update] Starting automatic update process..."
echo "[Update] This will pull latest code, rebuild, and restart the container"

# Pull latest code on host
echo "[Update] Pulling latest code..."
docker run --rm \
  -v "${INSTALL_DIR}:${INSTALL_DIR}" \
  alpine/git:latest \
  -C "${INSTALL_DIR}" pull origin main

# Get the Docker group ID from the socket to run docker commands
echo "[Update] Rebuilding Docker image..."
docker build -t "${APP_NAME}" "${INSTALL_DIR}"

echo "[Update] Stopping current container..."
docker stop "${CONTAINER_NAME}" || true

echo "[Update] Removing old container..."
docker rm "${CONTAINER_NAME}" || true

echo "[Update] Reading runtime configuration..."
# Detect if TensorRT engine exists
TENSORRT_MOUNT=""
if [ -f "${INSTALL_DIR}/yolov8n.engine" ]; then
  TENSORRT_MOUNT="-v ${INSTALL_DIR}/yolov8n.engine:/app/yolov8n.engine"
fi

# Get environment variables from old container (if any)
DETECTION_INTERVAL=$(docker inspect "${CONTAINER_NAME}" 2>/dev/null | grep -oP 'DETECTION_INTERVAL=\K[^"]+' || echo "")
INFERENCE_WIDTH=$(docker inspect "${CONTAINER_NAME}" 2>/dev/null | grep -oP 'INFERENCE_WIDTH=\K[^"]+' || echo "")

PERF_ENV=""
if [ ! -z "${DETECTION_INTERVAL}" ]; then
  PERF_ENV="${PERF_ENV} -e DETECTION_INTERVAL=${DETECTION_INTERVAL}"
fi
if [ ! -z "${INFERENCE_WIDTH}" ]; then
  PERF_ENV="${PERF_ENV} -e INFERENCE_WIDTH=${INFERENCE_WIDTH}"
fi

echo "[Update] Starting new container..."
docker run -d \
  --restart unless-stopped \
  --runtime nvidia \
  --gpus all \
  -p 8080:8080 \
  --name "${CONTAINER_NAME}" \
  -v ~/.aws:/root/.aws \
  -v "${INSTALL_DIR}/config:/app/config" \
  -v /usr/bin/docker:/usr/bin/docker \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /usr/bin/curl:/usr/bin/curl \
  -v /usr/bin/bash:/usr/bin/bash \
  ${TENSORRT_MOUNT} \
  ${PERF_ENV} \
  "${APP_NAME}"

echo "[Update] Update complete! New container is starting..."
echo "[Update] Check status with: docker logs ${CONTAINER_NAME}"
