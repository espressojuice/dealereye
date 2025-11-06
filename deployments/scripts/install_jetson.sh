#!/bin/bash
# DealerEye Jetson Edge Complete Installation Script
# One-line install: curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/deployments/scripts/install_jetson.sh | bash -s -- <TENANT_ID> <SITE_ID> <MQTT_HOST>

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

# Parse arguments or use defaults
TENANT_ID=${1:-"1d3021aa-5c8d-4afc-bb89-c3cea7a1f19d"}
SITE_ID=${2:-"95f2d9e7-3d72-4eda-9705-4faf83c5edfc"}
MQTT_HOST=${3:-"localhost"}
MQTT_PORT=${4:-"1883"}
EDGE_ID="edge-$(hostname)"

echo "Configuration:"
echo "  Tenant ID: $TENANT_ID"
echo "  Site ID: $SITE_ID"
echo "  Edge ID: $EDGE_ID"
echo "  MQTT: $MQTT_HOST:$MQTT_PORT"
echo ""

# Update system
echo "Updating system..."
$SUDO apt-get update -qq

# Install prerequisites
echo "Installing prerequisites..."
$SUDO apt-get install -y python3-pip git curl wget mosquitto-clients

# Check for DeepStream
if dpkg -l | grep -q deepstream-7.1; then
    echo "✓ DeepStream 7.1 already installed"
else
    echo "Installing DeepStream 7.1..."
    $SUDO apt-get install -y deepstream-7.1
    echo "✓ DeepStream 7.1 installed"
fi

# Install TensorRT Python bindings
echo "Installing TensorRT Python bindings..."
$SUDO apt-get install -y python3-libnvinfer python3-libnvinfer-dev libnvinfer-bin

echo ""
echo "Installing to: /opt/dealereye"

# Create directory structure
echo "Creating directories..."
$SUDO mkdir -p /opt/dealereye/{edge,shared,models,config,logs}
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
echo "Copying code..."
cp -r /opt/dealereye/code/edge/* /opt/dealereye/edge/ 2>/dev/null || true
cp -r /opt/dealereye/code/shared /opt/dealereye/ 2>/dev/null || true

# Copy config files
echo "Copying configuration files..."
cp /opt/dealereye/code/deployments/config/*.txt /opt/dealereye/config/
cp /opt/dealereye/code/deployments/config/edge_config.env /opt/dealereye/.env

# Update edge config with provided values
sed -i "s/^EDGE_ID=.*/EDGE_ID=$EDGE_ID/" /opt/dealereye/.env
sed -i "s/^TENANT_ID=.*/TENANT_ID=$TENANT_ID/" /opt/dealereye/.env
sed -i "s/^SITE_ID=.*/SITE_ID=$SITE_ID/" /opt/dealereye/.env
sed -i "s/^MQTT_BROKER_HOST=.*/MQTT_BROKER_HOST=$MQTT_HOST/" /opt/dealereye/.env
sed -i "s/^MQTT_BROKER_PORT=.*/MQTT_BROKER_PORT=$MQTT_PORT/" /opt/dealereye/.env

# Install Python dependencies
echo "Installing Python dependencies..."
cd /opt/dealereye
pip3 install --user ultralytics paho-mqtt pydantic pydantic-settings pynvml numpy opencv-python

# Download YOLO model
echo ""
echo "Setting up YOLO model..."
cd /opt/dealereye/models

if [ ! -f yolov8n.onnx ]; then
    echo "Downloading and exporting YOLOv8n to ONNX..."
    cat > download_yolo.py << 'PYEOF'
from ultralytics import YOLO
print("Downloading YOLOv8n model...")
model = YOLO('yolov8n.pt')
print("Exporting to ONNX (without simplification for Jetson compatibility)...")
model.export(format='onnx', simplify=False)
print("✓ YOLO model ready")
PYEOF

    python3 download_yolo.py
    rm download_yolo.py
    echo "✓ YOLO ONNX model created"
else
    echo "✓ YOLO ONNX model exists"
fi

echo ""
echo "NOTE: TensorRT engine will be generated automatically by DeepStream on first run."
echo "This may take 2-5 minutes the first time a camera is started."

# Create systemd service
echo ""
echo "Creating systemd service..."
$SUDO tee /etc/systemd/system/dealereye-edge.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=DealerEye Edge Analytics Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/dealereye
EnvironmentFile=/opt/dealereye/.env
Environment=PYTHONPATH=/opt/dealereye
ExecStart=/usr/bin/python3 /opt/dealereye/edge/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Fix $USER in service file
$SUDO sed -i "s/\$USER/$USER/" /etc/systemd/system/dealereye-edge.service

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
echo "Configuration: /opt/dealereye/.env"
echo "DeepStream Config: /opt/dealereye/config/yolov8_config.txt"
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
