"""
CRUD operations for DealerEye control plane.
Database access layer with multi-tenant isolation.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from control-plane.storage.database import (
    TenantModel, SiteModel, CameraModel, ZoneModel, LineModel,
    UserModel, AlertModel, AlertRuleModel, EventModel, MetricModel
)
from shared.models.core import Tenant, Site, Camera, Zone, Line, User
from shared.models.alerts import Alert, AlertRule
from shared.schemas.events import BaseEvent
from shared.models.metrics import MetricValue


# ===== Tenants =====

def create_tenant(db: Session, tenant: Tenant) -> TenantModel:
    """Create new tenant."""
    db_tenant = TenantModel(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        settings=tenant.settings,
    )
    db.add(db_tenant)
    db.commit()
    db.refresh(db_tenant)
    return db_tenant


def get_tenant(db: Session, tenant_id: UUID) -> Optional[TenantModel]:
    """Get tenant by ID."""
    return db.query(TenantModel).filter(TenantModel.tenant_id == tenant_id).first()


# ===== Sites =====

def create_site(db: Session, site: Site) -> SiteModel:
    """Create new site."""
    db_site = SiteModel(
        site_id=site.site_id,
        tenant_id=site.tenant_id,
        name=site.name,
        timezone=site.timezone,
        address=site.address,
        business_hours=site.business_hours.model_dump(),
        settings=site.settings,
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    return db_site


def get_site(db: Session, site_id: UUID) -> Optional[SiteModel]:
    """Get site by ID."""
    return db.query(SiteModel).filter(SiteModel.site_id == site_id).first()


def list_tenant_sites(db: Session, tenant_id: UUID) -> List[SiteModel]:
    """List all sites for a tenant."""
    return db.query(SiteModel).filter(SiteModel.tenant_id == tenant_id).all()


# ===== Cameras =====

def create_camera(db: Session, camera: Camera) -> CameraModel:
    """Create new camera."""
    db_camera = CameraModel(
        camera_id=camera.camera_id,
        site_id=camera.site_id,
        name=camera.name,
        role=camera.role.value,
        rtsp_url=camera.rtsp_url,
        make_model=camera.make_model,
        status=camera.status.value,
        confidence_threshold=camera.confidence_threshold,
        intrinsics=camera.intrinsics.model_dump() if camera.intrinsics else None,
        extrinsics=camera.extrinsics.model_dump() if camera.extrinsics else None,
        health=camera.health.model_dump() if camera.health else None,
        settings=camera.settings,
    )
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


def get_camera(db: Session, camera_id: UUID) -> Optional[CameraModel]:
    """Get camera by ID."""
    return db.query(CameraModel).filter(CameraModel.camera_id == camera_id).first()


def update_camera(db: Session, camera_id: UUID, camera: Camera) -> Optional[CameraModel]:
    """Update camera."""
    db_camera = get_camera(db, camera_id)
    if not db_camera:
        return None

    db_camera.name = camera.name
    db_camera.role = camera.role.value
    db_camera.rtsp_url = camera.rtsp_url
    db_camera.status = camera.status.value
    db_camera.confidence_threshold = camera.confidence_threshold
    db_camera.settings = camera.settings

    db.commit()
    db.refresh(db_camera)
    return db_camera


def list_site_cameras(db: Session, site_id: UUID) -> List[CameraModel]:
    """List all cameras for a site."""
    return db.query(CameraModel).filter(CameraModel.site_id == site_id).all()


# ===== Zones =====

def create_zone(db: Session, zone: Zone) -> ZoneModel:
    """Create zone for camera."""
    db_zone = ZoneModel(
        zone_id=zone.zone_id,
        camera_id=zone.camera_id,
        name=zone.name,
        zone_type=zone.zone_type.value,
        points=[p.model_dump() for p in zone.points],
        dwell_threshold_seconds=zone.dwell_threshold_seconds,
        calibration_metadata=zone.calibration_metadata,
    )
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone


def list_camera_zones(db: Session, camera_id: UUID) -> List[ZoneModel]:
    """List all zones for a camera."""
    return db.query(ZoneModel).filter(ZoneModel.camera_id == camera_id).all()


# ===== Lines =====

def create_line(db: Session, line: Line) -> LineModel:
    """Create line for camera."""
    db_line = LineModel(
        line_id=line.line_id,
        camera_id=line.camera_id,
        name=line.name,
        line_type=line.line_type.value,
        points=[p.model_dump() for p in line.points],
        direction=line.direction,
        calibration_metadata=line.calibration_metadata,
    )
    db.add(db_line)
    db.commit()
    db.refresh(db_line)
    return db_line


def list_camera_lines(db: Session, camera_id: UUID) -> List[LineModel]:
    """List all lines for a camera."""
    return db.query(LineModel).filter(LineModel.camera_id == camera_id).all()


# ===== Events =====

def create_event(db: Session, event: BaseEvent) -> EventModel:
    """Store event in database."""
    db_event = EventModel(
        event_id=event.event_id,
        event_type=event.event_type.value,
        tenant_id=event.tenant_id,
        site_id=event.site_id,
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        attributes=event.model_dump(exclude={'event_id', 'event_type', 'tenant_id', 'site_id', 'camera_id', 'timestamp'}),
    )
    db.add(db_event)
    db.commit()
    return db_event


def query_events(
    db: Session,
    site_id: UUID,
    start_time: datetime,
    end_time: datetime,
    event_types: Optional[List[str]] = None,
    limit: int = 1000,
) -> List[EventModel]:
    """Query events for a site within time range."""
    query = db.query(EventModel).filter(
        and_(
            EventModel.site_id == site_id,
            EventModel.timestamp >= start_time,
            EventModel.timestamp <= end_time,
        )
    )

    if event_types:
        query = query.filter(EventModel.event_type.in_(event_types))

    return query.order_by(desc(EventModel.timestamp)).limit(limit).all()


# ===== Metrics =====

def create_metric(db: Session, metric: MetricValue) -> MetricModel:
    """Store computed metric."""
    db_metric = MetricModel(
        metric_id=metric.metric_id,
        tenant_id=metric.tenant_id,
        site_id=metric.site_id,
        metric_name=metric.metric_name.value,
        window_start=metric.window_start,
        window_size=metric.window_size.value,
        value=metric.value,
        unit=metric.unit,
        dimensions=metric.dimensions,
        is_estimated=metric.is_estimated,
    )
    db.add(db_metric)
    db.commit()
    return db_metric


def query_metrics(
    db: Session,
    site_id: UUID,
    metric_name: str,
    start_time: datetime,
    end_time: datetime,
    window_size: Optional[str] = None,
) -> List[MetricModel]:
    """Query metrics for a site."""
    query = db.query(MetricModel).filter(
        and_(
            MetricModel.site_id == site_id,
            MetricModel.metric_name == metric_name,
            MetricModel.window_start >= start_time,
            MetricModel.window_start <= end_time,
        )
    )

    if window_size:
        query = query.filter(MetricModel.window_size == window_size)

    return query.order_by(MetricModel.window_start).all()


# ===== Alerts =====

def create_alert_rule(db: Session, rule: AlertRule) -> AlertRuleModel:
    """Create alert rule."""
    db_rule = AlertRuleModel(
        rule_id=rule.rule_id,
        tenant_id=rule.tenant_id,
        site_id=rule.site_id,
        name=rule.name,
        description=rule.description,
        alert_type=rule.alert_type.value,
        severity=rule.severity.value,
        conditions=[c.model_dump() for c in rule.conditions],
        time_windows=[w.model_dump() for w in rule.time_windows],
        cooldown_seconds=rule.cooldown_seconds,
        channels=[c.value for c in rule.channels],
        recipients=rule.recipients,
        enabled=rule.enabled,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


def get_alert_rule(db: Session, rule_id: UUID) -> Optional[AlertRuleModel]:
    """Get alert rule by ID."""
    return db.query(AlertRuleModel).filter(AlertRuleModel.rule_id == rule_id).first()


def list_alert_rules(db: Session, tenant_id: UUID, site_id: Optional[UUID] = None) -> List[AlertRuleModel]:
    """List alert rules for tenant or site."""
    query = db.query(AlertRuleModel).filter(AlertRuleModel.tenant_id == tenant_id)
    if site_id:
        query = query.filter(AlertRuleModel.site_id == site_id)
    return query.all()


def create_alert(db: Session, alert: Alert) -> AlertModel:
    """Create alert instance."""
    db_alert = AlertModel(
        alert_id=alert.alert_id,
        tenant_id=alert.tenant_id,
        site_id=alert.site_id,
        rule_id=alert.rule_id,
        alert_type=alert.alert_type.value,
        severity=alert.severity.value,
        title=alert.title,
        message=alert.message,
        status=alert.status.value,
        context=alert.context,
        clip_url=alert.clip_url,
        keyframe_url=alert.keyframe_url,
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


def list_alerts(
    db: Session,
    site_id: UUID,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[AlertModel]:
    """List recent alerts for a site."""
    query = db.query(AlertModel).filter(AlertModel.site_id == site_id)

    if status:
        query = query.filter(AlertModel.status == status)

    return query.order_by(desc(AlertModel.triggered_at)).limit(limit).all()
