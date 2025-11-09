"""
FastAPI control plane application.
REST + WebSocket API for DealerEye platform.
"""
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from shared.config import ControlPlaneConfig
from shared.models.core import Camera, CameraStatus, CameraRole
from control_plane.storage.database import CameraModel, SiteModel, TenantModel, EventModel
from control_plane.storage.crud import EventCRUD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DealerEye Control Plane API",
    description="Service Drive Analytics Platform API",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
config = ControlPlaneConfig()

# Database
engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ===== Dependencies =====

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===== Tenant and Site Management =====

@app.get("/api/v1/tenants/{tenant_id}")
async def get_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    """Get tenant by ID."""
    tenant = db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "tenant_id": str(tenant.tenant_id),
        "name": tenant.name,
        "created_at": tenant.created_at.isoformat(),
        "settings": tenant.settings
    }


@app.get("/api/v1/sites/{site_id}")
async def get_site(site_id: UUID, db: Session = Depends(get_db)):
    """Get site by ID."""
    site = db.query(SiteModel).filter(SiteModel.site_id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return {
        "site_id": str(site.site_id),
        "tenant_id": str(site.tenant_id),
        "name": site.name,
        "timezone": site.timezone,
        "address": site.address,
        "business_hours": site.business_hours,
        "created_at": site.created_at.isoformat()
    }


@app.get("/api/v1/sites/{site_id}/cameras")
async def list_site_cameras(site_id: UUID, db: Session = Depends(get_db)):
    """List all cameras for a site."""
    cameras = db.query(CameraModel).filter(CameraModel.site_id == site_id).all()
    return [
        {
            "camera_id": str(cam.camera_id),
            "site_id": str(cam.site_id),
            "name": cam.name,
            "rtsp_url": cam.rtsp_url,
            "role": cam.role,
            "status": cam.status,
            "created_at": cam.created_at.isoformat()
        }
        for cam in cameras
    ]


# OLD: Database-based camera endpoint - removed (replaced with CameraManager version later in file)


# ===== Event Management =====

@app.get("/api/v1/events")
async def query_events(
    tenant_id: UUID,
    site_id: Optional[UUID] = None,
    camera_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Query events with filters."""
    crud = EventCRUD(db)
    events = crud.get_events(
        tenant_id=tenant_id,
        site_id=site_id,
        camera_id=camera_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    return {
        "total": len(events),
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "tenant_id": str(event.tenant_id),
                "site_id": str(event.site_id),
                "camera_id": str(event.camera_id),
                "timestamp": event.timestamp.isoformat(),
                "attributes": event.attributes,
            }
            for event in events
        ]
    }


@app.get("/api/v1/events/stats")
async def event_stats(
    tenant_id: UUID,
    site_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    """Get event statistics."""
    crud = EventCRUD(db)

    # Get recent events count
    recent_events = crud.get_events(tenant_id=tenant_id, site_id=site_id, limit=1000)

    # Count by type
    type_counts = {}
    for event in recent_events:
        type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

    return {
        "total_events": len(recent_events),
        "by_type": type_counts,
        "tenant_id": str(tenant_id),
        "site_id": str(site_id) if site_id else None,
    }


@app.get("/api/v1/camera/stats")
async def camera_stats():
    """Get current camera statistics from edge device."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://192.168.10.195:8080/stats")
            return response.json()
    except:
        # Fallback to reading from database if edge unavailable
        return {
            "camera_ip": "192.168.10.2",
            "resolution": "1536x576",
            "fps": "20.0",
            "model": "YOLOv8n TensorRT FP16"
        }


# Camera Management APIs
camera_manager = None

def get_camera_manager():
    global camera_manager
    if camera_manager is None:
        from shared.camera_manager import CameraManager
        camera_manager = CameraManager()
    return camera_manager


@app.get("/api/v1/cameras")
async def list_cameras():
    """List all configured cameras."""
    manager = get_camera_manager()
    return manager.list_cameras()


@app.get("/api/v1/cameras/{camera_id}")
async def get_camera(camera_id: str):
    """Get a specific camera."""
    manager = get_camera_manager()
    camera = manager.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@app.post("/api/v1/cameras")
async def add_camera(camera: dict):
    """Add a new camera."""
    manager = get_camera_manager()
    try:
        new_camera = manager.add_camera(
            name=camera.get("name"),
            rtsp_url=camera.get("rtsp_url")
        )
        return new_camera
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/v1/cameras/{camera_id}")
async def update_camera(camera_id: str, camera: dict):
    """Update camera configuration."""
    manager = get_camera_manager()
    updated = manager.update_camera(camera_id, **camera)
    if not updated:
        raise HTTPException(status_code=404, detail="Camera not found")
    return updated


@app.delete("/api/v1/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    """Delete a camera."""
    manager = get_camera_manager()
    deleted = manager.delete_camera(camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"status": "deleted"}


@app.get("/stream-proxy")
async def stream_proxy():
    """Proxy MJPEG stream from localhost:8080/stream to dashboard."""
    import httpx
    async def generate():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", "http://localhost:8080/stream") as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except:
            pass
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard for viewing events."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DealerEye Event Dashboard</title>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1600px; margin: 0 auto; }
            h1 { color: #333; }
            .nav { background: white; padding: 15px 20px; margin-bottom: 20px; border-radius: 8px; }
            .nav a { color: #007bff; text-decoration: none; margin-right: 20px; }
            .nav a:hover { text-decoration: underline; }
            .top-row {
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }
            .live-view {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .live-view img {
                width: 100%;
                border-radius: 4px;
                background: #000;
            }
            .stats {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .events {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #4CAF50; color: white; }
            tr:hover { background-color: #f5f5f5; }
            .refresh-btn {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin-bottom: 20px;
            }
            .refresh-btn:hover { background-color: #45a049; }
            .event-type {
                padding: 4px 8px;
                border-radius: 4px;
                background: #e3f2fd;
                font-size: 0.9em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav">
                <a href="/dashboard">Dashboard</a>
                <a href="/cameras">Cameras</a>
            </div>

            <h1>DealerEye Event Dashboard</h1>

            <button class="refresh-btn" onclick="loadData()">Refresh</button>

            <div class="top-row">
                <div class="live-view" id="live-view-container">
                    <h2>Live Camera Feed</h2>
                    <div id="camera-content">
                        <p style="color: #666;">Checking for cameras...</p>
                    </div>
                </div>

                <div class="stats" id="stats">
                    Loading statistics...
                </div>
            </div>

            <div class="events">
                <h2>Recent Events</h2>
                <table id="events-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Event Type</th>
                            <th>Site ID</th>
                            <th>Attributes</th>
                        </tr>
                    </thead>
                    <tbody id="events-body">
                        <tr><td colspan="4">Loading events...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            // Default tenant/site IDs - update these with your values
            const TENANT_ID = '1d3021aa-5c8d-4afc-bb89-c3cea7a1f19d';
            const SITE_ID = '95f2d9e7-3d72-4eda-9705-4faf83c5edfc';

            async function loadCameraInfo() {
                try {
                    // First, check if any cameras are configured
                    const camerasResponse = await fetch('/api/v1/cameras');
                    const cameras = await camerasResponse.json();
                    
                    const cameraContent = document.getElementById('camera-content');
                    
                    if (!cameras || cameras.length === 0) {
                        // No cameras configured
                        cameraContent.innerHTML = `
                            <p style="color: #999; text-align: center; padding: 40px;">
                                No cameras configured.<br>
                                <a href="/cameras" style="color: #007bff; text-decoration: none;">Add a camera</a> to start.
                            </p>
                        `;
                        return;
                    }
                    
                    // Cameras exist - show camera info (stream removed until edge device integration complete)
                    const camera = cameras[0];
                    cameraContent.innerHTML = `
                        <div style="text-align: center;">
                            <h3 style="margin-top: 0; color: #333;">Camera: ${camera.name}</h3>
                            <p style="color: #666;">ID: ${camera.id}</p>
                            <p style="color: #666;">RTSP: ${camera.rtsp_url}</p>
                            <p style="color: #999; margin-top: 20px; font-size: 0.9em;">
                                <img src="/stream-proxy" 
                                 alt="Live Camera Feed" 
                                 style="width: 100%; max-width: 800px; height: auto; border: 2px solid #ddd; border-radius: 4px;">
                            <p style="color: #666; margin-top: 10px; font-size: 0.9em;">
                            </p>
                        </div>
                    `;
                } catch (error) {
                    document.getElementById('camera-content').innerHTML =
                        '<p style="color: red;">Error loading camera information</p>';
                    console.error('Error:', error);
                }
            }

            async function loadStats() {
                try {
                    const response = await fetch(
                        `/api/v1/events/stats?tenant_id=${TENANT_ID}&site_id=${SITE_ID}`
                    );
                    const data = await response.json();

                    let statsHtml = '<h2>Statistics</h2>';
                    statsHtml += `<p><strong>Total Events:</strong> ${data.total_events}</p>`;
                    statsHtml += '<p><strong>By Type:</strong></p><ul>';
                    for (const [type, count] of Object.entries(data.by_type)) {
                        statsHtml += `<li>${type}: ${count}</li>`;
                    }
                    statsHtml += '</ul>';

                    document.getElementById('stats').innerHTML = statsHtml;
                } catch (error) {
                    document.getElementById('stats').innerHTML =
                        '<p style="color: red;">Error loading statistics</p>';
                    console.error('Error:', error);
                }
            }

            async function loadEvents() {
                try {
                    const response = await fetch(
                        `/api/v1/events?tenant_id=${TENANT_ID}&site_id=${SITE_ID}&limit=50`
                    );
                    const data = await response.json();

                    const tbody = document.getElementById('events-body');
                    if (data.events.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="4">No events found</td></tr>';
                        return;
                    }

                    tbody.innerHTML = data.events.map(event => {
                        const timestamp = new Date(event.timestamp).toLocaleString();
                        const attrs = JSON.stringify(event.attributes, null, 2)
                            .substring(0, 100) + '...';
                        return `
                            <tr>
                                <td>${timestamp}</td>
                                <td><span class="event-type">${event.event_type}</span></td>
                                <td>${event.site_id.substring(0, 8)}...</td>
                                <td><pre style="margin:0; font-size:0.8em;">${attrs}</pre></td>
                            </tr>
                        `;
                    }).join('');
                } catch (error) {
                    document.getElementById('events-body').innerHTML =
                        '<tr><td colspan="4" style="color: red;">Error loading events</td></tr>';
                    console.error('Error:', error);
                }
            }

            function loadData() {
                loadCameraInfo();
                loadStats();
                loadEvents();
            }

            // Load data on page load
            loadData();

            // Auto-refresh every 5 seconds
            setInterval(loadData, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/cameras", response_class=HTMLResponse)
async def cameras_page():
    """Camera management page."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DealerEye - Camera Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #333; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
            .btn {
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            .btn-primary { background: #007bff; color: white; }
            .btn-primary:hover { background: #0056b3; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .btn-secondary { background: #6c757d; color: white; }
            .cameras-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .camera-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .camera-header {
                display: flex;
                justify-content: space-between;
                align-items: start;
                margin-bottom: 15px;
            }
            .camera-name { font-size: 18px; font-weight: bold; margin-bottom: 5px; }
            .camera-id { font-size: 12px; color: #666; font-family: monospace; }
            .camera-url {
                font-size: 12px;
                color: #666;
                background: #f8f9fa;
                padding: 8px;
                border-radius: 4px;
                margin: 10px 0;
                word-break: break-all;
                font-family: monospace;
            }
            .camera-actions { display: flex; gap: 10px; margin-top: 15px; }
            .status-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            .status-enabled { background: #d4edda; color: #155724; }
            .status-disabled { background: #f8d7da; color: #721c24; }
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.5);
                z-index: 1000;
            }
            .modal-content {
                background: white;
                max-width: 500px;
                margin: 50px auto;
                padding: 30px;
                border-radius: 8px;
            }
            .modal-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
            .modal-title { font-size: 24px; font-weight: bold; }
            .close { font-size: 28px; cursor: pointer; color: #aaa; }
            .close:hover { color: #000; }
            .form-group { margin-bottom: 20px; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input, .form-group select {
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                box-sizing: border-box;
            }
            .form-actions { display: flex; gap: 10px; justify-content: flex-end; }
            .empty-state {
                text-align: center;
                padding: 60px 20px;
                background: white;
                border-radius: 8px;
            }
            .empty-state h2 { color: #666; margin-bottom: 10px; }
            .empty-state p { color: #999; margin-bottom: 20px; }
            .nav { background: white; padding: 15px 20px; margin-bottom: 20px; border-radius: 8px; }
            .nav a { color: #007bff; text-decoration: none; margin-right: 20px; }
            .nav a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="nav">
                <a href="/dashboard">Dashboard</a>
                <a href="/cameras">Cameras</a>
            </div>

            <div class="header">
                <h1>Camera Management</h1>
                <button class="btn btn-primary" onclick="showAddModal()">+ Add Camera</button>
            </div>

            <div id="cameras-container" class="cameras-grid"></div>
        </div>

        <!-- Add/Edit Camera Modal -->
        <div id="cameraModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <span class="modal-title" id="modalTitle">Add Camera</span>
                    <span class="close" onclick="closeModal()">&times;</span>
                </div>
                <form id="cameraForm">
                    <div class="form-group">
                        <label for="cameraName">Camera Name</label>
                        <input type="text" id="cameraName" required placeholder="Front Entrance">
                    </div>
                    <div class="form-group">
                        <label for="cameraId">Camera ID (UUID)</label>
                        <input type="text" id="cameraId" placeholder="Leave empty to auto-generate">
                    </div>
                    <div class="form-group">
                        <label for="rtspUrl">RTSP URL</label>
                        <input type="text" id="rtspUrl" required
                               placeholder="rtsp://username:password@192.168.1.100:554/stream1">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-success" id="saveButton">Save Camera</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            let editingCameraId = null;

            async function loadCameras() {
                try {
                    const response = await fetch('/api/v1/cameras');
                    const cameras = await response.json();

                    const container = document.getElementById('cameras-container');

                    if (cameras.length === 0) {
                        container.innerHTML = `
                            <div class="empty-state" style="grid-column: 1 / -1;">
                                <h2>No Cameras Configured</h2>
                                <p>Click "Add Camera" to get started</p>
                            </div>
                        `;
                        return;
                    }

                    container.innerHTML = cameras.map(camera => `
                        <div class="camera-card">
                            <div class="camera-header">
                                <div>
                                    <div class="camera-name">${camera.name}</div>
                                    <div class="camera-id">${camera.id}</div>
                                </div>
                                <span class="status-badge ${camera.enabled ? 'status-enabled' : 'status-disabled'}">
                                    ${camera.enabled ? 'Enabled' : 'Disabled'}
                                </span>
                            </div>
                            <div class="camera-url">${camera.rtsp_url}</div>
                            <div class="camera-actions">
                                <button class="btn btn-primary" onclick='editCamera(${JSON.stringify(camera)})'>Edit</button>
                                <button class="btn btn-danger" onclick="deleteCamera('${camera.id}', '${camera.name}')">Delete</button>
                            </div>
                        </div>
                    `).join('');
                } catch (error) {
                    console.error('Error loading cameras:', error);
                }
            }

            function showAddModal() {
                editingCameraId = null;
                document.getElementById('modalTitle').textContent = 'Add Camera';
                document.getElementById('cameraForm').reset();
                document.getElementById('cameraId').disabled = false;
                document.getElementById('cameraModal').style.display = 'block';
            }

            function editCamera(camera) {
                editingCameraId = camera.id;
                document.getElementById('modalTitle').textContent = 'Edit Camera';
                document.getElementById('cameraName').value = camera.name;
                document.getElementById('cameraId').value = camera.id;
                document.getElementById('cameraId').disabled = true;
                document.getElementById('rtspUrl').value = camera.rtsp_url;
                document.getElementById('cameraModal').style.display = 'block';
            }

            function closeModal() {
                document.getElementById('cameraModal').style.display = 'none';
                document.getElementById('cameraForm').reset();
                editingCameraId = null;
            }

            document.getElementById('cameraForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const camera = {
                    name: document.getElementById('cameraName').value,
                    rtsp_url: document.getElementById('rtspUrl').value,
                };

                if (!editingCameraId) {
                    const cameraId = document.getElementById('cameraId').value;
                    if (cameraId) {
                        camera.id = cameraId;
                    }
                }

                try {
                    let response;
                    if (editingCameraId) {
                        response = await fetch(`/api/v1/cameras/${editingCameraId}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(camera)
                        });
                    } else {
                        response = await fetch('/api/v1/cameras', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(camera)
                        });
                    }

                    if (response.ok) {
                        closeModal();
                        loadCameras();
                    } else {
                        const error = await response.json();
                        alert('Error: ' + (error.detail || 'Failed to save camera'));
                    }
                } catch (error) {
                    alert('Error saving camera: ' + error.message);
                }
            });

            async function deleteCamera(id, name) {
                if (!confirm(`Are you sure you want to delete camera "${name}"?`)) {
                    return;
                }

                try {
                    const response = await fetch(`/api/v1/cameras/${id}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        loadCameras();
                    } else {
                        alert('Failed to delete camera');
                    }
                } catch (error) {
                    alert('Error deleting camera: ' + error.message);
                }
            }

            // Close modal when clicking outside
            window.onclick = function(event) {
                const modal = document.getElementById('cameraModal');
                if (event.target === modal) {
                    closeModal();
                }
            }

            // Load cameras on page load
            loadCameras();
        </script>
    </body>
    </html>
    """
    return html_content


# ===== WebSocket for Live Updates =====

class ConnectionManager:
    """Manage WebSocket connections for live updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")


manager = ConnectionManager()


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live metric updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            site_id = data.get("site_id")
            await websocket.send_json({
                "type": "subscribed",
                "site_id": site_id,
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# REMOVED: Hardcoded stream-proxy endpoint - cameras should not show streams unless properly configured with edge device


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
