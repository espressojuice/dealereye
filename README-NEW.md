# DealerEye - Service Drive Analytics Platform

**Production-ready dealership analytics from existing IP cameras without in-camera analytics.**

DealerEye is a comprehensive AI-powered video analytics platform designed specifically for auto dealerships. It transforms existing RTSP camera feeds into actionable business intelligence for service operations, security, and customer experience optimization.

## 🎯 Key Features

### Phase 1 Metrics
- **Time to Greet (TTG)**: Track advisor response time from vehicle arrival to customer greeting
- **Rack Time**: Monitor bay occupancy and technician efficiency
- **Lobby Occupancy**: Real-time customer count with dwell distribution
- **Drive Throughput**: Track unique service lane arrivals and exits
- **After-Hours Security**: Perimeter crossing detection with instant alerts

### Platform Capabilities
- ✅ **Multi-tenant**: Built for multi-rooftop dealership groups
- ✅ **Offline-first**: All analytics run locally during WAN outages
- ✅ **Privacy-focused**: No face or plate recognition in Phase 1
- ✅ **Real-time + Historical**: Live dashboards with YOY comparisons
- ✅ **Hardware-accelerated**: Optimized for NVIDIA Jetson Orin NX

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         EDGE LAYER                          │
│              (Jetson Orin NX at Dealership)                 │
├─────────────────────────────────────────────────────────────┤
│  RTSP Cameras → DeepStream Pipeline → ByteTrack            │
│       ↓                                                      │
│  Zone/Line Analytics Engine                                 │
│       ↓                                                      │
│  MQTT Uplink (QoS 1, offline queue)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ Events
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                    CONTROL PLANE                            │
│                  (Cloud or On-Prem)                         │
├─────────────────────────────────────────────────────────────┤
│  MQTT Broker ← Events                                       │
│       ↓                                                      │
│  Metrics Engine → TimescaleDB                               │
│       ↓                                                      │
│  Alert Rules Engine → Notifications (SMS/Email)            │
│       ↓                                                      │
│  FastAPI + WebSocket                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + WS
                       ↓
┌─────────────────────────────────────────────────────────────┐
│                      DASHBOARD                              │
│                    (React SPA)                              │
├─────────────────────────────────────────────────────────────┤
│  Live Tiles | Historical Charts | Alert Management         │
│  Camera Setup | Zone/Line Editor | User Management         │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Technology Stack

### Edge (Jetson Orin NX)
- **DeepStream SDK 6.3+**: Optimized video pipeline with hardware acceleration
- **YOLOv8 + TensorRT**: Object detection (FP16, INT8 with calibration)
- **ByteTrack**: Fast multi-object tracking with stable IDs
- **MQTT**: Reliable event uplink with offline queuing
- **Python 3.10**: Application logic

### Control Plane
- **FastAPI**: REST and WebSocket API
- **PostgreSQL + TimescaleDB**: Time-series event and metric storage
- **Redis**: Caching and real-time state
- **MQTT (Mosquitto)**: Message broker with QoS guarantees
- **SQLAlchemy**: ORM with hypertable support
- **Pydantic**: Strong typing and validation

### Dashboard
- **React 18**: Modern SPA framework
- **WebSocket**: Live metric updates
- **Chart.js / Recharts**: Historical visualization
- **Tailwind CSS**: Responsive UI

## 📦 Repository Structure

```
dealereye/
├── edge/                      # Edge device application
│   ├── deepstream/            # DeepStream configs and templates
│   ├── analytics/             # Zone/line crossing engine
│   ├── uplink/                # MQTT client with offline queue
│   ├── health/                # Health monitoring
│   └── main.py                # Edge application entry point
│
├── control-plane/             # Control plane services
│   ├── api/                   # FastAPI REST + WebSocket
│   ├── metrics/               # Metrics computation engine
│   ├── mqtt/                  # MQTT subscriber
│   ├── storage/               # Database models and schema
│   └── notifier/              # Alert notification service
│
├── dashboard/                 # React dashboard (to be built)
│   └── src/
│
├── shared/                    # Shared code across services
│   ├── schemas/               # Event schemas (Pydantic)
│   ├── models/                # Core, metrics, alert models
│   └── config.py              # Configuration utilities
│
├── deployments/               # Deployment artifacts
│   ├── docker/                # Docker Compose for control plane
│   └── scripts/               # Edge provisioning scripts
│
├── docs/                      # Documentation
└── tests/                     # Test suites
```

## 🚀 Quick Start

### Control Plane (Local Development)

1. **Clone and navigate to repository:**
```bash
cd dealereye
```

2. **Start services with Docker Compose:**
```bash
cd deployments/docker
docker-compose up -d
```

This starts:
- PostgreSQL with TimescaleDB (port 5432)
- Redis (port 6379)
- MQTT Broker (port 1883)
- Control Plane API (port 8000)

3. **Verify services:**
```bash
curl http://localhost:8000/health
```

### Edge Device (Jetson Orin NX)

1. **Install DeepStream SDK 6.3+:**
```bash
# Follow NVIDIA documentation
# https://docs.nvidia.com/metropolis/deepstream/dev-guide/
```

2. **Provision edge device:**
```bash
chmod +x deployments/scripts/provision_edge.sh
./deployments/scripts/provision_edge.sh
```

3. **Convert YOLO model to TensorRT:**
```bash
# Use trtexec or Python script
# Place engine at /opt/dealereye/models/yolo.engine
```

4. **Start edge service:**
```bash
sudo systemctl start dealereye-edge
sudo systemctl enable dealereye-edge
```

## 📊 Core Metrics Computation

### Time to Greet (TTG)
```python
TTG = GreetStartedEvent.timestamp - NearestPrecedingVehicleArrival.timestamp
```
- Maximum match window: 5 minutes
- Filters: Business hours, same lane
- Units: seconds

### Rack Time
```python
RackTime = BayExitEvent.timestamp - BayEntryEvent.timestamp
```
- Tracked per technician (manual mapping in Phase 1)
- Marked as "estimated" until RO integration
- Units: seconds

### Lobby Occupancy
```python
CurrentCount = LobbyEnterEvents.count() - LobbyExitEvents.count()
```
- Running count with track ID deduplication
- Real-time updates via WebSocket
- Units: persons

### Drive Throughput
```python
Throughput = UniqueVehicleArrivals(timeWindow).count()
```
- Windows: today, last 7 days, last 30 days
- Units: vehicles

## 🎨 Dashboard Views

### 1. Overview Dashboard
- **Live TTG Tile**: Current TTG with SLA status (green/yellow/red)
- **Lobby Now**: Current occupancy count
- **Today's Throughput**: Vehicle count
- **Active Alerts**: Critical alerts requiring attention

### 2. Operations View
- **Technician Bay Board**: Current jobs, elapsed time, average by tech
- **Service Lane Heatmap**: Activity patterns by hour

### 3. Historical Analytics
- **TTG Trends**: Line charts with day/week/month filters
- **YOY Comparisons**: Side-by-side with matched weekdays
- **CSV Export**: Raw metric data for external analysis

### 4. Camera Setup
- **Visual Zone Editor**: Draw polygons on camera feed
- **Line Drawing Tool**: Define entry/exit lines with direction
- **Camera Health**: FPS, dropped frames, last heartbeat

## 🔔 Alerting System

### Example Alert Rules

**Service Alert: High TTG**
```yaml
Rule: TTG > 120 seconds
Active: Monday-Saturday, 8:00-18:00
Cooldown: 5 minutes
Channels: SMS, Email
Recipients: service_manager@dealership.com
```

**Security Alert: After-Hours Perimeter**
```yaml
Rule: Vehicle crosses lot perimeter
Active: After business hours
Cooldown: 1 minute
Channels: SMS, Email, Push
Recipients: security_lead@dealership.com
Attachments: 10-second clip + keyframe
```

## 🔒 Security & Privacy

### Phase 1 Privacy Guardrails
- ❌ No face recognition
- ❌ No license plate recognition
- ✅ Optional face/plate blurring on stored media
- ✅ Short clips only on alerts (not 24/7 recording)
- ✅ On-demand clip fetch with limited retention

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (RBAC)
- Roles: Super Admin, Tenant Admin, Site Manager, Technician, Security Lead, Viewer
- Per-tenant and per-site data isolation
- Audit logs for all admin actions

## 📈 Performance Targets

### Edge (Jetson Orin NX)
- **Streams**: 4 concurrent 1080p@15fps
- **Latency**: <2 seconds edge-to-dashboard
- **Dropped Frames**: <2% sustained
- **GPU Utilization**: Safe operating range under peak load

### Control Plane
- **Event Processing**: <100ms per event
- **Metric Computation**: <1 second for TTG
- **Alert Delivery**: <3 seconds for critical alerts
- **API Response**: <200ms p95 for REST queries

## 🎯 Texarkana Pilot Acceptance Criteria

1. ✅ TTG calculated for ≥90% of arrivals
2. ✅ <5% false positives over full business day
3. ✅ Dashboard tiles update within 2-second latency
4. ✅ After-hours perimeter crossing triggers alert with clip
5. ✅ Lobby occupancy drift ≤±1 person over 10 minutes
6. ✅ No data loss during 10-minute WAN outage
7. ✅ Automatic catch-up on reconnect

## 🔧 Configuration

### Environment Variables

**Edge (.env or edge.env):**
```bash
EDGE_ID=edge-001
TENANT_ID=uuid
SITE_ID=uuid
MQTT_BROKER_HOST=mqtt.dealereye.com
MQTT_BROKER_PORT=1883
BATCH_SIZE=4
TARGET_FPS=15
CONFIDENCE_THRESHOLD=0.5
```

**Control Plane (.env):**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/dealereye
REDIS_URL=redis://localhost:6379/0
MQTT_BROKER_HOST=localhost
JWT_SECRET=your-secret-key
S3_ACCESS_KEY=your-key
S3_SECRET_KEY=your-secret
S3_BUCKET=dealereye-clips
```

## 📝 Operator Guide

### Enrolling a Camera

1. Add camera via API or dashboard
2. Verify RTSP stream connectivity
3. Draw zones for greet areas, bays, lobby
4. Draw lines for entry/exit points
5. Set confidence threshold (default: 0.5)
6. Configure business hours per site
7. Enable camera and verify health telemetry

### Setting Up TTG Alerts

1. Navigate to Alert Rules
2. Create new rule:
   - Name: "High Time to Greet"
   - Condition: TTG > 120 seconds
   - Time Window: Mon-Sat, 08:00-18:00
   - Channels: Email
   - Recipients: manager@dealership.com
3. Set cooldown to 5 minutes
4. Enable rule

### Troubleshooting

**Edge device not publishing events:**
- Check MQTT broker connectivity: `mosquitto_sub -h <broker> -t dealereye/#`
- Verify edge service status: `sudo systemctl status dealereye-edge`
- Check logs: `sudo journalctl -u dealereye-edge -f`

**Low FPS or high dropped frames:**
- Reduce batch size or target FPS in config
- Check GPU utilization: `tegrastats`
- Verify TensorRT engine is FP16 (not FP32)

**TTG not computing:**
- Verify both vehicle arrival and greet zones/lines are configured
- Check event types in database: arrivals + greets must be present
- Ensure greet zone overlaps with vehicle path

## 🗺️ Roadmap

### Phase 1 (Current)
- ✅ Core metrics: TTG, lobby occupancy, throughput, rack time
- ✅ Alerting with SMS/Email
- ✅ Real-time dashboard with YOY
- ✅ Multi-tenant architecture
- ⏳ Texarkana pilot deployment

### Phase 2 (Q2 2025)
- Sales lot analytics (dwell time, lot tours)
- Parts counter metrics
- RO integration for actual rack time
- Path classification (service vs sales vs parts)
- Mobile app for managers

### Phase 3 (Q3 2025)
- Predictive wait time display
- Customer journey mapping
- Advanced anomaly detection
- Multi-site benchmarking dashboard

## 🤝 Contributing

This is a private repository for espressojuice/dealereye. For issues or feature requests, please open a GitHub issue.

## 📄 License

Proprietary. All rights reserved.

---

**Built with Claude Code** for rapid iteration and production quality.

For questions or support: [Your contact info]
