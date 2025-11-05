#!/bin/bash
# Edge device provisioning script for NVIDIA Jetson Orin NX
# Configures a new edge device for a site

set -e

echo "=========================================="
echo "DealerEye Edge Device Provisioning"
echo "=========================================="

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "Warning: Not running on NVIDIA Jetson device"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Prompt for configuration
read -p "Enter Tenant ID: " TENANT_ID
read -p "Enter Site ID: " SITE_ID
read -p "Enter Edge ID (unique identifier for this device): " EDGE_ID
read -p "Enter MQTT Broker Host: " MQTT_HOST
read -p "Enter MQTT Broker Port [1883]: " MQTT_PORT
MQTT_PORT=${MQTT_PORT:-1883}

echo ""
echo "Configuration Summary:"
echo "  Tenant ID: $TENANT_ID"
echo "  Site ID: $SITE_ID"
echo "  Edge ID: $EDGE_ID"
echo "  MQTT Broker: $MQTT_HOST:$MQTT_PORT"
echo ""
read -p "Confirm configuration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Provisioning cancelled"
    exit 1
fi

# Create directory structure
echo "Creating directory structure..."
sudo mkdir -p /opt/dealereye/{edge,models,config,logs}
sudo chown -R $USER:$USER /opt/dealereye

# Create configuration file
echo "Creating edge configuration..."
cat > /opt/dealereye/config/edge.env <<EOF
# DealerEye Edge Configuration
EDGE_ID=$EDGE_ID
TENANT_ID=$TENANT_ID
SITE_ID=$SITE_ID

# MQTT Configuration
MQTT_BROKER_HOST=$MQTT_HOST
MQTT_BROKER_PORT=$MQTT_PORT
MQTT_QOS=1

# Video Processing
BATCH_SIZE=4
TARGET_FPS=15
CONFIDENCE_THRESHOLD=0.5

# Paths
DEEPSTREAM_CONFIG_PATH=/opt/dealereye/config/deepstream_config.txt
YOLO_ENGINE_PATH=/opt/dealereye/models/yolo.engine
BYTETRACK_CONFIG_PATH=/opt/dealereye/config/bytetrack_config.txt
EOF

echo "Configuration saved to /opt/dealereye/config/edge.env"

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev

# Check for DeepStream
if [ ! -d "/opt/nvidia/deepstream" ]; then
    echo ""
    echo "WARNING: DeepStream SDK not found at /opt/nvidia/deepstream"
    echo "Please install DeepStream 6.3+ before running the edge application"
    echo "Installation guide: https://docs.nvidia.com/metropolis/deepstream/dev-guide/"
    echo ""
fi

# Install Python dependencies
echo "Installing Python dependencies..."
cd /opt/dealereye/edge
pip3 install -r requirements.txt

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/dealereye-edge.service > /dev/null <<EOF
[Unit]
Description=DealerEye Edge Analytics Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/dealereye/edge
EnvironmentFile=/opt/dealereye/config/edge.env
ExecStart=/usr/bin/python3 /opt/dealereye/edge/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo ""
echo "=========================================="
echo "Provisioning Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy your YOLO model to /opt/dealereye/models/"
echo "2. Convert YOLO to TensorRT engine (see documentation)"
echo "3. Configure cameras via control plane API"
echo "4. Start the edge service:"
echo "   sudo systemctl start dealereye-edge"
echo "   sudo systemctl enable dealereye-edge"
echo ""
echo "View logs:"
echo "   sudo journalctl -u dealereye-edge -f"
echo ""
