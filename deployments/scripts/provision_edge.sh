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
    echo "This is OK for testing, but production deployments need Jetson hardware"
fi

# Prompt for configuration
echo ""
echo "Enter configuration details:"
read -p "Tenant ID: " TENANT_ID
read -p "Site ID: " SITE_ID
read -p "Edge ID (unique identifier): " EDGE_ID
read -p "MQTT Broker Host: " MQTT_HOST
read -p "MQTT Broker Port [1883]: " MQTT_PORT
MQTT_PORT=${MQTT_PORT:-1883}

echo ""
echo "Configuration Summary:"
echo "  Tenant ID: $TENANT_ID"
echo "  Site ID: $SITE_ID"
echo "  Edge ID: $EDGE_ID"
echo "  MQTT Broker: $MQTT_HOST:$MQTT_PORT"
echo ""
read -p "Confirm? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 1
fi

# Create directory structure
echo "Creating directories..."
sudo mkdir -p /opt/dealereye/{edge,models,config,logs}
sudo chown -R $USER:$USER /opt/dealereye

# Create configuration file
echo "Creating edge configuration..."
cat > /opt/dealereye/config/edge.env <<ENVEOF
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
ENVEOF

echo "✓ Configuration saved to /opt/dealereye/config/edge.env"

# Clone or update code
if [ -d /opt/dealereye/edge ]; then
    echo "Updating existing code..."
    cd /opt/dealereye && git pull origin main
else
    echo "Cloning DealerEye code..."
    cd /opt/dealereye
    git clone https://github.com/espressojuice/dealereye.git code
    cp -r code/edge code/shared /opt/dealereye/
fi

# Install dependencies
echo "Installing Python dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install -r /opt/dealereye/edge/requirements.txt

echo ""
echo "=========================================="
echo "✓ Edge Device Provisioned!"
echo "=========================================="
echo ""
echo "Configuration: /opt/dealereye/config/edge.env"
echo ""
echo "Next steps:"
echo "1. Install DeepStream SDK (if not already installed)"
echo "2. Copy YOLO model to /opt/dealereye/models/"
echo "3. Test MQTT connection:"
echo "   mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -t 'dealereye/#'"
echo ""
echo "For production, create systemd service to auto-start edge app"
echo ""
