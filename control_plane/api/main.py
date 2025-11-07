"""
FastAPI control plane application.
REST + WebSocket API for DealerEye platform.
"""
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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


@app.post("/api/v1/cameras")
async def create_camera(camera_data: dict, db: Session = Depends(get_db)):
    """Create a new camera."""
    camera = CameraModel(
        site_id=UUID(camera_data["site_id"]),
        name=camera_data["name"],
        rtsp_url=camera_data["rtsp_url"],
        role=camera_data.get("camera_role", "GENERAL"),
        status="INACTIVE",
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)

    return {
        "camera_id": str(camera.camera_id),
        "site_id": str(camera.site_id),
        "name": camera.name,
        "rtsp_url": camera.rtsp_url,
        "role": camera.role,
        "status": camera.status,
        "created_at": camera.created_at.isoformat()
    }


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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard for viewing events."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DealerEye Event Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #333; }
            .stats {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
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
            <h1>DealerEye Event Dashboard</h1>

            <button class="refresh-btn" onclick="loadData()">Refresh</button>

            <div class="stats" id="stats">
                Loading statistics...
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
