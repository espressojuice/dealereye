# DealerEye Quick Start Guide

This guide will get you up and running with DealerEye in under 10 minutes.

## Prerequisites

- **Docker Desktop** (for control plane services)
- **Python 3.10+** (for control plane and scripts)
- **Node.js 18+** (for dashboard)
- **NVIDIA Jetson Orin NX** (for edge deployment)

## Local Development Setup

### 1. Start Control Plane Services

```bash
# Clone and navigate to repository
cd dealereye

# Quick start (starts Docker services and initializes DB)
./start.sh

# Or manually:
cd deployments/docker
docker-compose up -d
```

This starts:
- PostgreSQL with TimescaleDB (port 5432)
- Redis (port 6379)
- MQTT Broker (port 1883)
- FastAPI Control Plane (port 8000)

### 2. Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### 3. Start Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard will be available at: http://localhost:3000

## Testing the System

### Send Test Event via MQTT

```bash
# Install mosquitto client
brew install mosquitto  # macOS
# or: sudo apt-get install mosquitto-clients  # Linux

# Publish test event
mosquitto_pub -h localhost -t "dealereye/TENANT_ID/SITE_ID/events" \
  -m '{"event_type":"vehicle_arrival","tenant_id":"...","site_id":"...","camera_id":"...","timestamp":"2024-01-01T10:00:00Z","track_id":"track_1","line_id":"...","confidence":0.95}'
```

### Query Metrics via API

```bash
# Get Time to Greet metrics
curl "http://localhost:8000/api/v1/metrics/time_to_greet?site_id=SITE_ID&start_time=2024-01-01T00:00:00Z&end_time=2024-01-01T23:59:59Z"

# List cameras
curl http://localhost:8000/api/v1/sites/SITE_ID/cameras
```

## Edge Device Setup (Jetson Orin NX)

### 1. Prerequisites

- Install **DeepStream SDK 6.3+**
- Install **CUDA Toolkit**
- Install **TensorRT**

```bash
# On Jetson
sudo apt-get update
sudo apt-get install python3-pip
```

### 2. Provision Edge Device

```bash
# Copy provisioning script to Jetson
scp deployments/scripts/provision_edge.sh jetson@192.168.1.100:/tmp/

# SSH to Jetson
ssh jetson@192.168.1.100

# Run provisioning
cd /tmp
chmod +x provision_edge.sh
./provision_edge.sh
```

Follow prompts to enter:
- Tenant ID
- Site ID
- Edge ID
- MQTT Broker Host/Port

### 3. Install YOLO Model

```bash
# On your workstation, download YOLOv8
pip install ultralytics
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx')"

# Copy to Jetson
scp yolov8n.onnx jetson@192.168.1.100:/opt/dealereye/models/

# On Jetson, convert to TensorRT
trtexec --onnx=/opt/dealereye/models/yolov8n.onnx \
        --saveEngine=/opt/dealereye/models/yolo.engine \
        --fp16
```

### 4. Start Edge Service

```bash
# On Jetson
sudo systemctl start dealereye-edge
sudo systemctl enable dealereye-edge

# View logs
sudo journalctl -u dealereye-edge -f
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Control Plane
DATABASE_URL=postgresql://dealereye:password@localhost:5432/dealereye
MQTT_BROKER_HOST=localhost
JWT_SECRET=your-secret-key

# Edge
EDGE_ID=edge-001
TENANT_ID=your-tenant-uuid
SITE_ID=your-site-uuid
MQTT_BROKER_HOST=mqtt.yourdomain.com
```

### Camera Enrollment

1. Navigate to Dashboard → Cameras
2. Click "Add Camera"
3. Enter RTSP URL: `rtsp://username:password@camera-ip:554/stream`
4. Select camera role (service_lane, lobby, etc.)
5. Draw zones and lines on camera preview
6. Save configuration

Edge device will automatically receive updated configuration via MQTT.

## Common Commands

```bash
# View control plane logs
cd deployments/docker
docker-compose logs -f api

# View MQTT messages
mosquitto_sub -h localhost -t "dealereye/#" -v

# Restart services
docker-compose restart

# Stop everything
docker-compose down

# Reset database
docker-compose down -v
./start.sh
```

## Troubleshooting

### Services won't start
```bash
# Check Docker
docker ps

# Check port conflicts
lsof -i :8000  # API
lsof -i :5432  # PostgreSQL
lsof -i :1883  # MQTT
```

### Edge device not publishing
```bash
# On Jetson, check service status
sudo systemctl status dealereye-edge

# Check MQTT connectivity
mosquitto_sub -h YOUR_MQTT_HOST -t '#' -v

# Check logs
sudo journalctl -u dealereye-edge -n 100
```

### Dashboard not connecting
```bash
# Check API is running
curl http://localhost:8000/health

# Check WebSocket
wscat -c ws://localhost:8000/ws/live
```

## Next Steps

1. **Configure cameras**: Add your IP cameras via dashboard
2. **Set up zones**: Draw greet zones, bay entry/exit lines
3. **Create alert rules**: Define TTG thresholds and notification channels
4. **Monitor metrics**: View live dashboard and historical analytics

For detailed documentation, see [README-NEW.md](README-NEW.md).

## Support

For issues or questions:
- GitHub Issues: https://github.com/espressojuice/dealereye/issues
- Email: [Your contact]

---

**Built for Texarkana dealerships and beyond** 🚗
