"""
FastAPI control plane application.
REST + WebSocket API for DealerEye platform.
"""
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from shared.config import ControlPlaneConfig
from shared.models.core import Camera, CameraStatus, CameraRole
from control_plane.storage.database import CameraModel, SiteModel, TenantModel

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
