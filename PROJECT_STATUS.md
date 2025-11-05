# DealerEye - Project Status

**Last Updated**: November 4, 2024
**Status**: Foundation Complete - Ready for Development

---

## ✅ COMPLETED

### Architecture & Design
- [x] Multi-tenant platform architecture defined
- [x] Event-driven design with MQTT message bus
- [x] Tech stack selected: DeepStream + ByteTrack + FastAPI + React
- [x] Database schema with TimescaleDB for time-series
- [x] Offline-first edge design with event buffering

### Shared Foundation
- [x] 34 Python modules created
- [x] Strong typing with Pydantic models
- [x] 11 domain event types defined
- [x] Core models (Tenant, Site, Camera, Zone, Line, User)
- [x] Metrics models (TTG, lobby, throughput, rack time)
- [x] Alert models with rules engine
- [x] Configuration utilities for edge and control plane

### Edge Application (Jetson Orin NX)
- [x] DeepStream pipeline configurations (YOLO + ByteTrack)
- [x] Zone & line crossing analytics engine
- [x] Dwell detection and greet proximity logic
- [x] MQTT uplink client (QoS 1, offline queue, auto-reconnect)
- [x] Health monitoring (GPU, FPS, dropped frames)
- [x] Main application orchestrator
- [x] Jetson provisioning script with systemd service

### Control Plane
- [x] SQLAlchemy models with TimescaleDB support
- [x] FastAPI application skeleton
- [x] MQTT subscriber for event ingestion
- [x] Metrics computation engine (TTG, rack time, lobby, throughput)
- [x] CRUD operations for all entities
- [x] Alert notification service (SMS via Twilio, Email via SMTP, Webhooks)
- [x] WebSocket support for live updates

### Deployment
- [x] Docker Compose with Postgres, Redis, MQTT
- [x] Dockerfiles for containerized services
- [x] Database initialization script with sample data
- [x] Quick start script (start.sh)
- [x] Environment configuration templates

### Dashboard
- [x] React + Vite + TypeScript setup
- [x] Tailwind CSS configuration
- [x] Overview page with metric tiles
- [x] Navigation and routing
- [x] WebSocket client skeleton
- [x] View stubs (Operations, Historical, Alerts, Cameras)

### Documentation
- [x] Comprehensive README with architecture
- [x] Quick start guide
- [x] Operator guide sections
- [x] Performance targets defined
- [x] Acceptance criteria documented

---

## 🚧 IN PROGRESS / TODO

### High Priority (Texarkana Pilot)

#### Dashboard UI (Critical)
- [ ] Complete Operations view with bay board
- [ ] Historical charts with Recharts/Chart.js
- [ ] Alert management UI (acknowledge/resolve)
- [ ] Camera enrollment flow with ONVIF discovery
- [ ] Zone/line drawing tool (canvas overlay on video feed)
- [ ] Real-time metric updates via WebSocket
- [ ] YOY comparison view

#### API Implementation (Critical)
- [ ] Connect CRUD operations to API endpoints
- [ ] Implement JWT authentication
- [ ] RBAC enforcement on all endpoints
- [ ] Database session management
- [ ] Error handling and validation
- [ ] API integration tests

#### Edge DeepStream (Critical)
- [ ] Actual GStreamer pipeline implementation
- [ ] DeepStream Python bindings integration
- [ ] Probe callbacks for metadata extraction
- [ ] Zone/line config generator from database
- [ ] Camera health heartbeat implementation
- [ ] Clip extraction and upload on alerts

#### YOLO Model
- [ ] Train or download YOLOv8 model
- [ ] Convert to ONNX format
- [ ] Optimize to TensorRT (FP16/INT8)
- [ ] Calibration dataset from dealership footage
- [ ] Model validation and accuracy testing

### Medium Priority

#### Alert Rules Engine
- [ ] Rule evaluation loop
- [ ] Cooldown tracking
- [ ] Business hours checking
- [ ] Alert delivery coordination
- [ ] Delivery result persistence

#### Metrics Engine Enhancements
- [ ] Windowed aggregations (1m, 5m, 15m, 1h, 1d)
- [ ] YOY comparison logic with matched weekdays
- [ ] Percentile calculations (p95, p99)
- [ ] Metric export to CSV

#### Observability
- [ ] Structured logging with context
- [ ] Metrics export (Prometheus)
- [ ] Distributed tracing (optional)
- [ ] Grafana dashboards for ops
- [ ] Edge device monitoring dashboard

### Lower Priority (Post-Pilot)

#### Testing
- [ ] Unit tests for metrics engine
- [ ] Integration tests for MQTT flow
- [ ] E2E tests for API
- [ ] Load tests on Jetson (4 streams)
- [ ] Dashboard component tests

#### Production Hardening
- [ ] Environment-specific configs
- [ ] Secrets management (Vault or AWS Secrets Manager)
- [ ] Rate limiting on API
- [ ] Database connection pooling tuning
- [ ] Redis caching strategy
- [ ] Backup and restore procedures
- [ ] Disaster recovery plan

#### Features
- [ ] Multi-site dashboard with drill-down
- [ ] Technician assignment via UI
- [ ] RO system integration for actual rack times
- [ ] Path classification (service vs sales)
- [ ] Mobile app for managers
- [ ] SMS/Push notification preferences

---

## 📊 Current Metrics

- **Python Files**: 34
- **TypeScript Files**: 9
- **Docker Services**: 4 (Postgres, Redis, MQTT, API)
- **API Endpoints**: 20+ (stubs)
- **Event Types**: 11
- **Data Models**: 15+
- **Lines of Code**: ~4,500

---

## 🎯 Path to Texarkana Pilot

### Week 1: Core Functionality
1. Complete API with database operations
2. Implement JWT auth and RBAC
3. Build dashboard Overview and Historical views
4. Test MQTT event flow end-to-end

### Week 2: Edge Integration
1. DeepStream pipeline implementation
2. Zone/line configuration sync from API
3. YOLO model deployment and testing
4. Health monitoring and heartbeat

### Week 3: Analytics & Alerts
1. Metrics computation testing with real events
2. Alert rules engine implementation
3. Notification delivery (SMS/Email)
4. Dashboard alert management

### Week 4: Camera Setup & Testing
1. Camera enrollment UI
2. Zone/line drawing tool
3. Performance benchmarking on Jetson
4. End-to-end system testing

### Week 5: Pilot Deployment
1. Deploy to Texarkana site
2. Configure cameras and zones
3. Set up alert rules
4. Training and documentation
5. Monitor and tune

---

## 🔑 Key Decisions Made

1. **DeepStream over GStreamer**: Better performance and NVIDIA support
2. **ByteTrack over DeepSORT**: Faster, simpler, good enough for use case
3. **MQTT over NATS**: Industry standard for IoT, mature, well-documented
4. **TimescaleDB over InfluxDB**: Better SQL integration, easier queries
5. **React over Vue**: Larger ecosystem, more components available
6. **Vite over Create React App**: Faster builds, modern tooling
7. **Python path naming**: control_plane instead of control-plane (hyphens break imports)

---

## 🚨 Known Issues & Risks

### Technical Risks
- **DeepStream complexity**: Steep learning curve, may need NVIDIA consulting
- **Low-light performance**: Need IR-capable cameras or calibration
- **Occlusion handling**: May need multiple camera angles
- **Track ID stability**: ByteTrack may lose IDs across occlusions
- **INT8 calibration**: Requires labeled dealership-specific dataset

### Operational Risks
- **WAN dependency**: Edge must work offline (mitigated with buffer)
- **Camera configuration**: Manual zone/line setup is tedious
- **False positives**: May need tuning period after deployment
- **Bandwidth**: Clip uploads may saturate connection (rate limit needed)

### Mitigation Strategies
- Start with FP16 TensorRT, only use INT8 if performance requires
- Allow per-camera confidence thresholds
- Implement adaptive FPS based on GPU load
- Add "estimated" badges on metrics lacking sensor data
- Plan for iterative tuning in first 2 weeks post-deployment

---

## 📞 Next Steps

**Immediate** (This Week):
1. Implement full API endpoints with database
2. Build dashboard components (Overview, Historical)
3. Test Docker Compose stack locally
4. Create development MQTT event simulator

**Short-Term** (Next 2 Weeks):
1. DeepStream pipeline with actual video processing
2. YOLO model training or fine-tuning
3. Alert rules engine
4. Camera setup UI

**Medium-Term** (1 Month):
1. Texarkana pilot deployment
2. Performance benchmarking
3. Operator training
4. Monitoring and tuning

---

## 🎉 What's Working

- ✅ Clean, modular architecture
- ✅ Strong typing throughout
- ✅ Multi-tenant from day one
- ✅ Offline-first design
- ✅ Production-ready deployment setup
- ✅ Comprehensive documentation

The foundation is **solid**. The main work ahead is:
1. **Dashboard UI** (React components and charts)
2. **API implementation** (wire up CRUD to endpoints)
3. **DeepStream integration** (Python bindings with actual video)

---

**Ready to ship to Texarkana in 4-5 weeks with focused execution.**
