"""
CRUD operations for database models.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from control_plane.storage.database import EventModel, CameraModel
from shared.schemas.events import BaseEvent


class EventCRUD:
    """CRUD operations for events."""

    def __init__(self, db: Session):
        self.db = db

    def create_event(
        self,
        tenant_id: str,
        site_id: str,
        event: BaseEvent,
    ) -> EventModel:
        """
        Create a new event in the database.

        Args:
            tenant_id: Tenant ID
            site_id: Site ID
            event: Event object

        Returns:
            Created EventModel
        """
        # Convert string IDs to UUID
        tenant_uuid = UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
        site_uuid = UUID(site_id) if isinstance(site_id, str) else site_id

        # Create event model
        db_event = EventModel(
            event_id=uuid4(),
            event_type=event.event_type,
            tenant_id=tenant_uuid,
            site_id=site_uuid,
            camera_id=event.camera_id,
            timestamp=event.timestamp,
            attributes=event.model_dump(mode='json', exclude={"event_type", "camera_id", "timestamp"}),
        )

        self.db.add(db_event)
        self.db.commit()
        self.db.refresh(db_event)

        return db_event

    def get_events(
        self,
        tenant_id: UUID,
        site_id: Optional[UUID] = None,
        camera_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EventModel]:
        """
        Query events with filters.

        Args:
            tenant_id: Tenant ID
            site_id: Optional site ID filter
            camera_id: Optional camera ID filter
            event_type: Optional event type filter
            start_time: Optional start timestamp
            end_time: Optional end timestamp
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of EventModel
        """
        query = self.db.query(EventModel).filter(EventModel.tenant_id == tenant_id)

        if site_id:
            query = query.filter(EventModel.site_id == site_id)

        if camera_id:
            query = query.filter(EventModel.camera_id == camera_id)

        if event_type:
            query = query.filter(EventModel.event_type == event_type)

        if start_time:
            query = query.filter(EventModel.timestamp >= start_time)

        if end_time:
            query = query.filter(EventModel.timestamp <= end_time)

        query = query.order_by(EventModel.timestamp.desc())
        query = query.limit(limit).offset(offset)

        return query.all()

    def count_events(
        self,
        tenant_id: UUID,
        site_id: Optional[UUID] = None,
        camera_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Count events matching filters.

        Args:
            tenant_id: Tenant ID
            site_id: Optional site ID filter
            camera_id: Optional camera ID filter
            event_type: Optional event type filter
            start_time: Optional start timestamp
            end_time: Optional end timestamp

        Returns:
            Event count
        """
        query = self.db.query(EventModel).filter(EventModel.tenant_id == tenant_id)

        if site_id:
            query = query.filter(EventModel.site_id == site_id)

        if camera_id:
            query = query.filter(EventModel.camera_id == camera_id)

        if event_type:
            query = query.filter(EventModel.event_type == event_type)

        if start_time:
            query = query.filter(EventModel.timestamp >= start_time)

        if end_time:
            query = query.filter(EventModel.timestamp <= end_time)

        return query.count()


class CameraCRUD:
    """CRUD operations for cameras."""

    def __init__(self, db: Session):
        self.db = db

    def get_camera(self, camera_id: UUID) -> Optional[CameraModel]:
        """Get camera by ID."""
        return self.db.query(CameraModel).filter(CameraModel.camera_id == camera_id).first()

    def get_cameras(self, site_id: UUID) -> List[CameraModel]:
        """Get all cameras for a site."""
        return self.db.query(CameraModel).filter(CameraModel.site_id == site_id).all()

    def update_camera_health(self, camera_id: UUID, health: dict):
        """Update camera health status."""
        camera = self.get_camera(camera_id)
        if camera:
            camera.health = health
            self.db.commit()
