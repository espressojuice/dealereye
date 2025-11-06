#!/bin/bash
# DealerEye Jetson Edge Complete Installation Script
# One-line install: curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/deployments/scripts/install_jetson.sh | bash

set -e

echo "=========================================="
echo "  DealerEye Jetson Edge Installer"
echo "=========================================="
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Error: This must be run on an NVIDIA Jetson device"
    exit 1
fi

# Get Jetson info
JETSON_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
echo "Detected: $JETSON_MODEL"
echo ""

# Check sudo
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# Update system
echo "Updating system..."
$SUDO apt-get update -qq

# Install prerequisites
echo "Installing prerequisites..."
$SUDO apt-get install -y python3-pip git curl wget mosquitto-clients

# Check for DeepStream
if [ -d "/opt/nvidia/deepstream/deepstream" ]; then
    DEEPSTREAM_VERSION=$(cat /opt/nvidia/deepstream/deepstream/version | head -1 || echo "unknown")
    echo "✓ DeepStream $DEEPSTREAM_VERSION already installed"
else
    echo ""
    echo "DeepStream SDK not found."
    echo "Installing DeepStream 6.4..."

    # Download and install DeepStream
    cd /tmp
    wget --quiet https://developer.download.nvidia.com/embedded/L4T/r36_Release_v4.0/DeepStream_6.4_Jetson_L4T_r36.4.tar.gz || {
        echo "Error: Could not download DeepStream. Please install manually:"
        echo "https://developer.nvidia.com/deepstream-sdk"
        exit 1
    }

    $SUDO tar -xf DeepStream_6.4_Jetson_L4T_r36.4.tar.gz -C /
    cd /opt/nvidia/deepstream/deepstream-6.4
    $SUDO ./install.sh

    echo "✓ DeepStream installed"
fi

# Prompt for configuration
echo ""
echo "=========================================="
echo "Configuration"
echo "=========================================="
read -p "Tenant ID: " TENANT_ID
read -p "Site ID: " SITE_ID
read -p "Edge ID [edge-$(hostname)]: " EDGE_ID
EDGE_ID=${EDGE_ID:-edge-$(hostname)}
read -p "MQTT Broker Host: " MQTT_HOST
read -p "MQTT Broker Port [1883]: " MQTT_PORT
MQTT_PORT=${MQTT_PORT:-1883}

echo ""
echo "Installing to: /opt/dealereye"

# Create directory structure
echo "Creating directories..."
$SUDO mkdir -p /opt/dealereye/{edge,models,config,logs}
$SUDO chown -R $USER:$USER /opt/dealereye

# Clone repository
if [ -d /opt/dealereye/code ]; then
    echo "Updating code..."
    cd /opt/dealereye/code
    git pull origin main
else
    echo "Cloning DealerEye..."
    git clone https://github.com/espressojuice/dealereye.git /opt/dealereye/code
fi

# Copy code to /opt
cp -r /opt/dealereye/code/edge/* /opt/dealereye/edge/
cp -r /opt/dealereye/code/shared /opt/dealereye/

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r /opt/dealereye/edge/requirements.txt -q

# Create configuration
echo "Creating configuration..."
cat > /opt/dealereye/config/edge.env << EOF
EDGE_ID=$EDGE_ID
TENANT_ID=$TENANT_ID
SITE_ID=$SITE_ID
MQTT_BROKER_HOST=$MQTT_HOST
MQTT_BROKER_PORT=$MQTT_PORT
MQTT_QOS=1
BATCH_SIZE=4
TARGET_FPS=15
CONFIDENCE_THRESHOLD=0.5
DEEPSTREAM_CONFIG_PATH=/opt/dealereye/config/deepstream_config.txt
YOLO_ENGINE_PATH=/opt/dealereye/models/yolov8n.engine
BYTETRACK_CONFIG_PATH=/opt/dealereye/config/bytetrack_config.txt
EOF

# Download YOLO model
echo ""
echo "Setting up YOLO model..."
if [ ! -f /opt/dealereye/models/yolov8n.onnx ]; then
    echo "Downloading YOLOv8n..."
    pip3 install -q ultralytics
    cd /opt/dealereye/models
    python3 << PYEOF
from ultralytics import YOLO
model = YOLO('yolov8n.pt')
model.export(format='onnx', simplify=True)
print("✓ YOLO model exported to ONNX")
PYEOF
    mv yolov8n.onnx /opt/dealereye/models/
else
    echo "✓ YOLO ONNX model exists"
fi

# Convert to TensorRT
echo "Converting YOLO to TensorRT (this may take a few minutes)..."
if [ ! -f /opt/dealereye/models/yolov8n.engine ]; then
    cd /opt/dealereye/models
    /usr/src/tensorrt/bin/trtexec \
        --onnx=yolov8n.onnx \
        --saveEngine=yolov8n.engine \
        --fp16 \
        --verbose 2>&1 | grep -E "Completed|Time|fps|Engine"
    echo "✓ TensorRT engine created"
else
    echo "✓ TensorRT engine exists"
fi

# Copy DeepStream configs
cp /opt/dealereye/code/edge/deepstream/*.txt /opt/dealereye/config/

# Create systemd service
echo "Creating systemd service..."
$SUDO tee /etc/systemd/system/dealereye-edge.service > /dev/null << EOF
[Unit]
Description=DealerEye Edge Analytics Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/dealereye/edge
EnvironmentFile=/opt/dealereye/config/edge.env
Environment=PYTHONPATH=/opt/dealereye
ExecStart=/usr/bin/python3 /opt/dealereye/edge/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

$SUDO systemctl daemon-reload

# Test MQTT connection
echo ""
echo "Testing MQTT connection..."
timeout 2 mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -t 'dealereye/test' -C 1 >/dev/null 2>&1 && {
    echo "✓ MQTT broker accessible"
} || {
    echo "⚠️  Could not reach MQTT broker at $MQTT_HOST:$MQTT_PORT"
    echo "   Make sure your control plane is running"
}

echo ""
echo "=========================================="
echo "✅ DealerEye Edge Installation Complete!"
echo "=========================================="
echo ""
echo "Configuration: /opt/dealereye/config/edge.env"
echo "Logs: /opt/dealereye/logs/"
echo ""
echo "Quick start:"
echo ""
echo "  # Start edge service"
echo "  sudo systemctl start dealereye-edge"
echo ""
echo "  # Enable auto-start on boot"
echo "  sudo systemctl enable dealereye-edge"
echo ""
echo "  # View logs"
echo "  sudo journalctl -u dealereye-edge -f"
echo ""
echo "  # Check status"
echo "  sudo systemctl status dealereye-edge"
echo ""
echo "Next steps:"
echo "  1. Add cameras via control plane API"
echo "  2. Configure zones and lines"
echo "  3. Start the edge service"
echo ""
echo "Control Plane API: http://$MQTT_HOST:8000/docs"
echo ""
