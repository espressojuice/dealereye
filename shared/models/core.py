"""
Core data models for DealerEye platform.
Multi-tenant from day one with site and tenant isolation.
"""
from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from uuid import UUID, uuid4


class CameraRole(str, Enum):
    """Camera role semantics for analytics."""
    SERVICE_LANE = "service_lane"
    LOBBY = "lobby"
    OIL_BAY = "oil_bay"
    TECHNICIAN_BAY = "technician_bay"
    LOT_PERIMETER = "lot_perimeter"
    SALES_LOT_ENTRY = "sales_lot_entry"
    PARTS_COUNTER = "parts_counter"


class CameraStatus(str, Enum):
    """Camera operational status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    CONFIGURING = "configuring"


class ZoneType(str, Enum):
    """Zone semantics for analytics."""
    GREET_ZONE = "greet_zone"
    BAY = "bay"
    LOBBY = "lobby"
    WAITING_AREA = "waiting_area"
    PERIMETER = "perimeter"
    PARKING = "parking"
    CUSTOM = "custom"


class LineType(str, Enum):
    """Line semantics for analytics."""
    ENTRY = "entry"
    EXIT = "exit"
    BAY_ENTRY = "bay_entry"
    BAY_EXIT = "bay_exit"
    DOOR = "door"
    PERIMETER = "perimeter"
    CUSTOM = "custom"


class UserRole(str, Enum):
    """Role-based access control roles."""
    SUPER_ADMIN = "super_admin"  # Cross-tenant admin
    TENANT_ADMIN = "tenant_admin"  # Tenant-level admin
    SITE_MANAGER = "site_manager"  # GM or service manager
    TECHNICIAN = "technician"  # Read-only technician view
    SECURITY_LEAD = "security_lead"  # Security alerts and video access
    VIEWER = "viewer"  # Read-only viewer


# ===== Core Models =====

class Tenant(BaseModel):
    """Multi-rooftop dealership group."""
    tenant_id: UUID = Field(default_factory=uuid4)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    settings: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class BusinessHours(BaseModel):
    """Business hours configuration."""
    open_time: time  # e.g., 08:00
    close_time: time  # e.g., 18:00
    days_of_week: List[int] = Field(default=[0, 1, 2, 3, 4, 5])  # 0=Monday, 6=Sunday

    def is_business_hours(self, dt: datetime) -> bool:
        """Check if datetime falls within business hours."""
        if dt.weekday() not in self.days_of_week:
            return False
        current_time = dt.time()
        return self.open_time <= current_time <= self.close_time


class Site(BaseModel):
    """Individual dealership location."""
    site_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str
    timezone: str = "America/Chicago"  # IANA timezone
    business_hours: BusinessHours = Field(
        default=BusinessHours(open_time=time(8, 0), close_time=time(18, 0))
    )
    address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    settings: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class CameraIntrinsics(BaseModel):
    """Camera intrinsic parameters for calibration."""
    focal_length_x: float
    focal_length_y: float
    principal_point_x: float
    principal_point_y: float
    distortion_coeffs: Optional[List[float]] = None


class CameraExtrinsics(BaseModel):
    """Camera extrinsic parameters (position and orientation)."""
    rotation: List[float]  # 3x3 rotation matrix flattened
    translation: List[float]  # 3D translation vector
    height_meters: Optional[float] = None


class CameraHealthSummary(BaseModel):
    """Camera health metrics."""
    last_heartbeat: datetime
    fps: float
    dropped_frames_pct: float
    uptime_seconds: int
    gpu_utilization_pct: Optional[float] = None


class Camera(BaseModel):
    """IP camera configuration."""
    camera_id: UUID = Field(default_factory=uuid4)
    site_id: UUID
    name: str
    role: CameraRole
    rtsp_url: str
    make_model: Optional[str] = None
    status: CameraStatus = CameraStatus.CONFIGURING
    intrinsics: Optional[CameraIntrinsics] = None
    extrinsics: Optional[CameraExtrinsics] = None
    health: Optional[CameraHealthSummary] = None
    confidence_threshold: float = 0.5  # Per-camera detection threshold
    created_at: datetime = Field(default_factory=datetime.utcnow)
    settings: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class Point(BaseModel):
    """2D point in image coordinates."""
    x: float
    y: float


class Zone(BaseModel):
    """Polygon zone for analytics."""
    zone_id: UUID = Field(default_factory=uuid4)
    camera_id: UUID
    name: str
    zone_type: ZoneType
    points: List[Point]  # Closed polygon vertices
    dwell_threshold_seconds: Optional[float] = None
    calibration_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("points")
    def validate_polygon(cls, v):
        if len(v) < 3:
            raise ValueError("Zone must have at least 3 points")
        return v

    class Config:
        use_enum_values = True


class Line(BaseModel):
    """Line for crossing detection."""
    line_id: UUID = Field(default_factory=uuid4)
    camera_id: UUID
    name: str
    line_type: LineType
    points: List[Point]  # Exactly 2 points
    direction: Optional[str] = None  # "forward" direction for counting
    calibration_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("points")
    def validate_line(cls, v):
        if len(v) != 2:
            raise ValueError("Line must have exactly 2 points")
        return v

    class Config:
        use_enum_values = True


class User(BaseModel):
    """System user with RBAC."""
    user_id: UUID = Field(default_factory=uuid4)
    tenant_id: Optional[UUID] = None  # None for super_admin
    email: str
    name: str
    role: UserRole
    site_ids: List[UUID] = Field(default_factory=list)  # Sites user can access
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        use_enum_values = True
