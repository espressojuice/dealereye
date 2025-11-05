"""
Database models and schema for DealerEye control plane.
Using SQLAlchemy with TimescaleDB for time-series data.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from uuid import uuid4
import enum

Base = declarative_base()


# ===== Tenants and Sites =====

class TenantModel(Base):
    __tablename__ = "tenants"

    tenant_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    settings = Column(JSONB, default={})

    # Relationships
    sites = relationship("SiteModel", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("UserModel", back_populates="tenant")


class SiteModel(Base):
    __tablename__ = "sites"

    site_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False)
    name = Column(String, nullable=False)
    timezone = Column(String, default="America/Chicago")
    address = Column(String)
    business_hours = Column(JSONB)  # Serialized BusinessHours
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSONB, default={})

    # Relationships
    tenant = relationship("TenantModel", back_populates="sites")
    cameras = relationship("CameraModel", back_populates="site", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sites_tenant_id", "tenant_id"),
    )


# ===== Cameras, Zones, Lines =====

class CameraStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISCONNECTED = "disconnected"
    CONFIGURING = "configuring"


class CameraModel(Base):
    __tablename__ = "cameras"

    camera_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id = Column(PGUUID(as_uuid=True), ForeignKey("sites.site_id"), nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # CameraRole enum
    rtsp_url = Column(String, nullable=False)
    make_model = Column(String)
    status = Column(SQLEnum(CameraStatusEnum), default=CameraStatusEnum.CONFIGURING)
    confidence_threshold = Column(Float, default=0.5)
    intrinsics = Column(JSONB)  # Serialized CameraIntrinsics
    extrinsics = Column(JSONB)  # Serialized CameraExtrinsics
    health = Column(JSONB)  # Serialized CameraHealthSummary
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSONB, default={})

    # Relationships
    site = relationship("SiteModel", back_populates="cameras")
    zones = relationship("ZoneModel", back_populates="camera", cascade="all, delete-orphan")
    lines = relationship("LineModel", back_populates="camera", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_cameras_site_id", "site_id"),
        Index("ix_cameras_status", "status"),
    )


class ZoneModel(Base):
    __tablename__ = "zones"

    zone_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    camera_id = Column(PGUUID(as_uuid=True), ForeignKey("cameras.camera_id"), nullable=False)
    name = Column(String, nullable=False)
    zone_type = Column(String, nullable=False)  # ZoneType enum
    points = Column(JSONB, nullable=False)  # List of Points
    dwell_threshold_seconds = Column(Float)
    calibration_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    camera = relationship("CameraModel", back_populates="zones")

    __table_args__ = (
        Index("ix_zones_camera_id", "camera_id"),
    )


class LineModel(Base):
    __tablename__ = "lines"

    line_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    camera_id = Column(PGUUID(as_uuid=True), ForeignKey("cameras.camera_id"), nullable=False)
    name = Column(String, nullable=False)
    line_type = Column(String, nullable=False)  # LineType enum
    points = Column(JSONB, nullable=False)  # Exactly 2 Points
    direction = Column(String)
    calibration_metadata = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    camera = relationship("CameraModel", back_populates="lines")

    __table_args__ = (
        Index("ix_lines_camera_id", "camera_id"),
    )


# ===== Events (TimescaleDB hypertable) =====

class EventModel(Base):
    __tablename__ = "events"

    event_id = Column(PGUUID(as_uuid=True), primary_key=True)
    event_type = Column(String, nullable=False)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=False)
    site_id = Column(PGUUID(as_uuid=True), nullable=False)
    camera_id = Column(PGUUID(as_uuid=True), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    attributes = Column(JSONB, default={})

    __table_args__ = (
        Index("ix_events_tenant_site_time", "tenant_id", "site_id", "timestamp"),
        Index("ix_events_type", "event_type"),
        Index("ix_events_camera_time", "camera_id", "timestamp"),
    )


# ===== Metrics (TimescaleDB hypertable) =====

class MetricModel(Base):
    __tablename__ = "metrics"

    metric_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=False)
    site_id = Column(PGUUID(as_uuid=True), nullable=False)
    metric_name = Column(String, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_size = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    dimensions = Column(JSONB, default={})
    is_estimated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_metrics_tenant_site_name_time", "tenant_id", "site_id", "metric_name", "window_start"),
        Index("ix_metrics_window", "window_start", "window_size"),
    )


# ===== Alerts =====

class AlertStatusEnum(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"


class AlertRuleModel(Base):
    __tablename__ = "alert_rules"

    rule_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=False)
    site_id = Column(PGUUID(as_uuid=True))  # Nullable for tenant-wide rules
    name = Column(String, nullable=False)
    description = Column(String)
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    conditions = Column(JSONB, nullable=False)
    time_windows = Column(JSONB, default=[])
    cooldown_seconds = Column(Integer, default=300)
    channels = Column(JSONB, nullable=False)
    recipients = Column(JSONB, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_alert_rules_tenant_site", "tenant_id", "site_id"),
        Index("ix_alert_rules_enabled", "enabled"),
    )


class AlertModel(Base):
    __tablename__ = "alerts"

    alert_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=False)
    site_id = Column(PGUUID(as_uuid=True), nullable=False)
    rule_id = Column(PGUUID(as_uuid=True), ForeignKey("alert_rules.rule_id"))
    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    status = Column(SQLEnum(AlertStatusEnum), default=AlertStatusEnum.OPEN)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(PGUUID(as_uuid=True))
    resolved_at = Column(DateTime)
    resolved_by = Column(PGUUID(as_uuid=True))
    context = Column(JSONB, default={})
    clip_url = Column(String)
    keyframe_url = Column(String)
    delivery_results = Column(JSONB, default=[])

    __table_args__ = (
        Index("ix_alerts_tenant_site_time", "tenant_id", "site_id", "triggered_at"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_rule_id", "rule_id"),
    )


# ===== Users and RBAC =====

class UserModel(Base):
    __tablename__ = "users"

    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.tenant_id"))
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # UserRole enum
    password_hash = Column(String, nullable=False)
    site_ids = Column(JSONB, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Relationships
    tenant = relationship("TenantModel", back_populates="users")

    __table_args__ = (
        Index("ix_users_tenant_id", "tenant_id"),
        Index("ix_users_email", "email"),
    )


# ===== Database Utilities =====

def create_database_engine(database_url: str):
    """Create database engine with connection pooling."""
    engine = create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
    )
    return engine


def init_database(engine):
    """Initialize database schema."""
    Base.metadata.create_all(engine)


def create_hypertables(engine):
    """
    Create TimescaleDB hypertables for time-series data.
    Must be run after init_database.
    """
    with engine.connect() as conn:
        # Convert events table to hypertable
        conn.execute(
            """
            SELECT create_hypertable('events', 'timestamp',
                                     if_not_exists => TRUE,
                                     chunk_time_interval => INTERVAL '1 day');
            """
        )

        # Convert metrics table to hypertable
        conn.execute(
            """
            SELECT create_hypertable('metrics', 'window_start',
                                     if_not_exists => TRUE,
                                     chunk_time_interval => INTERVAL '7 days');
            """
        )

        conn.commit()


def get_session_maker(engine):
    """Create session maker for database operations."""
    return sessionmaker(bind=engine)
