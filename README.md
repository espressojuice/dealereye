# DealerEye - Multi-Tenant Service Drive Analytics Platform

AI-powered video analytics platform for automotive dealerships. Edge-based computer vision with centralized management for multi-rooftop operations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Control Plane (Cloud/Server)            │
│  FastAPI + PostgreSQL/TimescaleDB + Redis + MQTT             │
│  - Multi-tenant management                                   │
│  - Metrics aggregation & storage                             │
│  - Alert rules engine                                        │
│  - REST + WebSocket API                                      │
│  - React dashboard                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ MQTT (QoS 1)
         ┌─────────────┴─────────────┬──────────────┐
         │                           │              │
┌────────▼────────┐         ┌────────▼────────┐   ...
│   Edge Device   │         │   Edge Device   │
│  (Jetson Orin)  │         │  (Jetson Orin)  │
│                 │         │                 │
│  - DeepStream   │         │  - DeepStream   │
│  - YOLOv8+TRT   │         │  - YOLOv8+TRT   │
│  - ByteTrack    │         │  - ByteTrack    │
│  - Zone/Line    │         │  - Zone/Line    │
│    Analytics    │         │    Analytics    │
│  - MQTT Uplink  │         │  - MQTT Uplink  │
│  - 24h Buffer   │         │  - 24h Buffer   │
└────────┬────────┘         └────────┬────────┘
         │                           │
    [IP Cameras]                [IP Cameras]
```

## Features

### Phase 1 Metrics
- **Time to Greet (TTG)**: Measure time from vehicle arrival to advisor interaction
- **Lobby Occupancy**: Real-time customer count in waiting areas
- **Rack Time**: Vehicle duration in service bays
- **Drive Throughput**: Unique vehicle count per hour/day

### Platform Capabilities
- **Multi-Tenant**: Support multiple dealership groups with data isolation
- **Edge Processing**: All AI runs on-site, no video leaves the premises
- **Offline-First**: 24-hour event buffering with automatic sync
- **Semantic Zones**: Define entry/exit lines, service bays, waiting areas
- **Real-time Alerts**: Configurable thresholds with SMS/Email/Webhook notifications
- **Time-Series Storage**: TimescaleDB for efficient metrics queries
- **RBAC**: Role-based access control (Admin, Manager, Viewer)

## Quick Start

### Control Plane Installation (Ubuntu Server)

One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash
```

This will:
- Install Docker & Docker Compose if needed
- Pull and start all services (PostgreSQL, Redis, MQTT, API)
- Initialize database with TimescaleDB
- Create sample tenant and site
- Display control plane URL

Access the API docs at: `http://<SERVER_IP>:8000/docs`

### Edge Device Installation (Jetson Orin NX)

**Prerequisites:**
- NVIDIA Jetson Orin NX with JetPack 6.1
- Control plane already running
- Network connectivity to control plane

**One-line install:**

```bash
# With default tenant/site (for testing)
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/deployments/scripts/install_jetson.sh | bash

# With custom tenant/site
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/deployments/scripts/install_jetson.sh | bash -s -- \
  <TENANT_ID> <SITE_ID> <MQTT_HOST>
```

This will:
- Install DeepStream 7.1 if not present
- Install TensorRT Python bindings
- Clone repository and copy code to /opt/dealereye
- Download YOLOv8n and export to ONNX
- Install Python dependencies
- Create systemd service
- Test MQTT connection

**Start the edge service:**

```bash
sudo systemctl start dealereye-edge
sudo systemctl enable dealereye-edge  # auto-start on boot

# View logs
sudo journalctl -u dealereye-edge -f
```

**Note:** TensorRT engine will be generated automatically by DeepStream on first camera startup (takes 2-5 minutes).

## Configuration

### Add Cameras via API

```bash
# Get tenant and site info
curl http://<CONTROL_PLANE>:8000/tenants

# Add a camera
curl -X POST http://<CONTROL_PLANE>:8000/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<TENANT_ID>",
    "site_id": "<SITE_ID>",
    "name": "Service Drive Entry",
    "rtsp_url": "rtsp://admin:password@192.168.1.100:554/stream",
    "camera_role": "DRIVE_ENTRY",
    "enabled": true
  }'
```

### Define Zones and Lines

```bash
# Create a crossing line for vehicle arrivals
curl -X POST http://<CONTROL_PLANE>:8000/lines \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<TENANT_ID>",
    "site_id": "<SITE_ID>",
    "camera_id": "<CAMERA_ID>",
    "name": "Service Drive Entry Line",
    "line_type": "ENTRY",
    "coordinates": [[100, 500], [1820, 500]],
    "direction": "UP_TO_DOWN"
  }'

# Create a zone for service bay
curl -X POST http://<CONTROL_PLANE>:8000/zones \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<TENANT_ID>",
    "site_id": "<SITE_ID>",
    "camera_id": "<CAMERA_ID>",
    "name": "Service Bay 1",
    "zone_type": "SERVICE_BAY",
    "coordinates": [[200, 100], [600, 100], [600, 800], [200, 800]]
  }'
```

### Alert Rules

```bash
# Alert if TTG > 5 minutes
curl -X POST http://<CONTROL_PLANE>:8000/alert-rules \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "<TENANT_ID>",
    "site_id": "<SITE_ID>",
    "name": "High Time to Greet",
    "metric_type": "TIME_TO_GREET",
    "condition": "GREATER_THAN",
    "threshold": 300,
    "window_seconds": 300,
    "cooldown_seconds": 900,
    "notification_channels": ["SMS", "EMAIL"],
    "recipient_emails": ["manager@dealership.com"],
    "recipient_phones": ["+15551234567"]
  }'
```

## API Endpoints

### Core Resources
- `GET /tenants` - List tenants
- `GET /sites` - List sites for tenant
- `GET /cameras` - List cameras
- `POST /cameras` - Add camera
- `GET /zones` - List zones
- `POST /zones` - Create zone
- `GET /lines` - List lines
- `POST /lines` - Create line

### Metrics
- `GET /metrics/ttg` - Time to Greet stats
- `GET /metrics/lobby-occupancy` - Current lobby count
- `GET /metrics/rack-time` - Service bay duration stats
- `GET /metrics/throughput` - Vehicle count per period

### Events
- `GET /events` - Query raw events
- `POST /events` - Create event (edge devices)

### Alerts
- `GET /alert-rules` - List alert rules
- `POST /alert-rules` - Create alert rule
- `GET /alerts` - List triggered alerts
- `PATCH /alerts/{id}` - Acknowledge/resolve alert

Full API documentation: `http://<CONTROL_PLANE>:8000/docs`

## System Requirements

### Control Plane
- **OS**: Ubuntu 20.04/22.04 LTS
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 100GB+ SSD (for time-series data)
- **Network**: Static IP or DNS name

### Edge Devices
- **Hardware**: NVIDIA Jetson Orin NX (16GB recommended)
- **OS**: JetPack 6.1 (Ubuntu 22.04)
- **GPU**: Orin NX with 1024 CUDA cores
- **Storage**: 128GB+ NVMe SSD
- **Network**: Gigabit Ethernet (for multiple high-res cameras)

### Cameras
- **Protocol**: RTSP/H.264
- **Resolution**: 1080p recommended
- **FPS**: 15-30 fps
- **Network**: PoE or WiFi with good signal strength

## Performance

### Edge Device (Jetson Orin NX)
- **YOLOv8n + TensorRT FP16**: 15-25ms inference @ 640px (40-65 FPS)
- **Concurrent Cameras**: 4-8 streams @ 1080p/15fps
- **DeepStream Pipeline**: Hardware-accelerated decode/encode
- **Tracking (ByteTrack)**: 5-10ms overhead per frame

### Control Plane
- **Event Ingestion**: 1000+ events/sec via MQTT
- **Metric Aggregation**: Real-time + batch processing
- **API Response**: <100ms p95
- **Database**: TimescaleDB with 1-year retention

## Troubleshooting

### Edge Device

**DeepStream won't start:**
```bash
# Check if DeepStream is installed
dpkg -l | grep deepstream

# Install if missing
sudo apt-get install -y deepstream-7.1
```

**TensorRT engine generation fails:**
- DeepStream will generate engine automatically on first run
- Check disk space: `df -h /opt/dealereye/models`
- View logs: `sudo journalctl -u dealereye-edge -n 100`

**MQTT connection fails:**
```bash
# Test MQTT broker
mosquitto_sub -h <CONTROL_PLANE> -p 1883 -t 'dealereye/#' -v

# Check firewall
sudo ufw status
sudo ufw allow 1883/tcp  # if blocked
```

**Camera stream errors:**
```bash
# Test RTSP with ffplay
ffplay -rtsp_transport tcp "rtsp://admin:pass@192.168.1.100:554/stream"

# Check network
ping 192.168.1.100
```

### Control Plane

**API not responding:**
```bash
# Check services
docker ps

# View logs
docker logs dealereye-api

# Restart services
cd /opt/dealereye
docker compose down && docker compose up -d
```

**Database connection errors:**
```bash
# Check PostgreSQL
docker logs dealereye-postgres

# Connect to database
docker exec -it dealereye-postgres psql -U dealereye -d dealereye
```

## Development

### Local Setup

```bash
# Clone repository
git clone https://github.com/espressojuice/dealereye.git
cd dealereye

# Start control plane services
cd deployments/docker
docker compose up -d

# Initialize database
python3 deployments/scripts/init_db.py --sample-data

# Install Python dependencies
pip3 install -r control_plane/requirements.txt
pip3 install -r edge/requirements.txt

# Run control plane API
cd control_plane
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure

```
dealereye/
├── shared/              # Shared models and schemas
│   ├── models/          # Pydantic data models
│   ├── schemas/         # Event schemas
│   └── config.py        # Configuration classes
├── edge/                # Edge device code
│   ├── analytics/       # Zone/line analytics engine
│   ├── uplink/          # MQTT publisher
│   ├── health/          # System monitoring
│   └── main.py          # Entry point
├── control_plane/       # Control plane services
│   ├── api/             # FastAPI application
│   ├── storage/         # Database models and CRUD
│   ├── metrics/         # Metrics aggregation engine
│   ├── mqtt/            # MQTT subscriber
│   └── notifier/        # Multi-channel notifications
├── dashboard/           # React dashboard (TBD)
├── deployments/
│   ├── docker/          # Docker Compose configs
│   ├── scripts/         # Installation scripts
│   └── config/          # DeepStream & edge configs
└── README.md
```

## Roadmap

### Phase 2 (Q2 2025)
- [ ] React dashboard with real-time metrics
- [ ] Mobile app for managers
- [ ] Advanced analytics (heatmaps, dwell time)
- [ ] Customer journey tracking

### Phase 3 (Q3 2025)
- [ ] License plate recognition (ALPR)
- [ ] VIN detection from windshield
- [ ] Integration with DMS systems
- [ ] Predictive scheduling

## License

MIT

## Support

Issues: https://github.com/espressojuice/dealereye/issues
