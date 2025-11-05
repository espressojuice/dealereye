"""
Domain event schemas for DealerEye analytics platform.
All events are strongly typed and include tenant/site context.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class EventType(str, Enum):
    """Domain event types emitted from the edge."""
    VEHICLE_ARRIVAL = "vehicle_arrival"
    VEHICLE_EXIT = "vehicle_exit"
    GREET_STARTED = "greet_started"
    BAY_ENTRY = "bay_entry"
    BAY_EXIT = "bay_exit"
    LOBBY_ENTER = "lobby_enter"
    LOBBY_EXIT = "lobby_exit"
    PERIMETER_CROSSING = "perimeter_crossing"
    SYSTEM_HEARTBEAT = "system_heartbeat"
    ZONE_DWELL = "zone_dwell"
    LINE_CROSSING = "line_crossing"


class ObjectClass(str, Enum):
    """Detected object classes."""
    PERSON = "person"
    VEHICLE = "vehicle"
    BICYCLE = "bicycle"
    MOTORCYCLE = "motorcycle"
    TRUCK = "truck"
    BUS = "bus"


class BaseEvent(BaseModel):
    """Base event with common fields for all domain events."""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    tenant_id: UUID
    site_id: UUID
    camera_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class VehicleArrivalEvent(BaseEvent):
    """Vehicle crosses entry line into service lane."""
    event_type: EventType = EventType.VEHICLE_ARRIVAL
    track_id: str
    line_id: UUID
    speed: Optional[float] = None  # mph, if calibrated
    confidence: float


class VehicleExitEvent(BaseEvent):
    """Vehicle crosses exit line from service lane."""
    event_type: EventType = EventType.VEHICLE_EXIT
    track_id: str
    line_id: UUID
    speed: Optional[float] = None
    confidence: float


class GreetStartedEvent(BaseEvent):
    """Person enters greet zone near a vehicle."""
    event_type: EventType = EventType.GREET_STARTED
    vehicle_track_id: str
    person_track_id: str
    zone_id: UUID
    proximity_seconds: float  # How long both have been in zone
    confidence: float


class BayEntryEvent(BaseEvent):
    """Vehicle enters a service bay."""
    event_type: EventType = EventType.BAY_ENTRY
    track_id: str
    bay_id: UUID
    confidence: float


class BayExitEvent(BaseEvent):
    """Vehicle exits a service bay."""
    event_type: EventType = EventType.BAY_EXIT
    track_id: str
    bay_id: UUID
    confidence: float


class LobbyEnterEvent(BaseEvent):
    """Person crosses lobby entry door line."""
    event_type: EventType = EventType.LOBBY_ENTER
    track_id: str
    door_id: UUID
    confidence: float


class LobbyExitEvent(BaseEvent):
    """Person crosses lobby exit door line."""
    event_type: EventType = EventType.LOBBY_EXIT
    track_id: str
    door_id: UUID
    confidence: float


class PerimeterCrossingEvent(BaseEvent):
    """After-hours crossing of lot perimeter."""
    event_type: EventType = EventType.PERIMETER_CROSSING
    track_id: str
    object_class: ObjectClass
    perimeter_id: UUID
    confidence: float
    is_after_hours: bool = True


class SystemHeartbeatEvent(BaseEvent):
    """Health telemetry from edge camera stream."""
    event_type: EventType = EventType.SYSTEM_HEARTBEAT
    fps: float
    dropped_frames_pct: float
    edge_uptime_seconds: int
    gpu_utilization_pct: Optional[float] = None
    memory_used_mb: Optional[int] = None


class ZoneDwellEvent(BaseEvent):
    """Object has dwelled in a zone beyond threshold."""
    event_type: EventType = EventType.ZONE_DWELL
    track_id: str
    object_class: ObjectClass
    zone_id: UUID
    dwell_seconds: float
    confidence: float


class LineCrossingEvent(BaseEvent):
    """Generic line crossing event."""
    event_type: EventType = EventType.LINE_CROSSING
    track_id: str
    object_class: ObjectClass
    line_id: UUID
    direction: str  # "forward" or "backward" relative to line definition
    confidence: float


# Event registry for deserialization
EVENT_REGISTRY = {
    EventType.VEHICLE_ARRIVAL: VehicleArrivalEvent,
    EventType.VEHICLE_EXIT: VehicleExitEvent,
    EventType.GREET_STARTED: GreetStartedEvent,
    EventType.BAY_ENTRY: BayEntryEvent,
    EventType.BAY_EXIT: BayExitEvent,
    EventType.LOBBY_ENTER: LobbyEnterEvent,
    EventType.LOBBY_EXIT: LobbyExitEvent,
    EventType.PERIMETER_CROSSING: PerimeterCrossingEvent,
    EventType.SYSTEM_HEARTBEAT: SystemHeartbeatEvent,
    EventType.ZONE_DWELL: ZoneDwellEvent,
    EventType.LINE_CROSSING: LineCrossingEvent,
}


def deserialize_event(data: Dict[str, Any]) -> BaseEvent:
    """Deserialize event from dict based on event_type."""
    event_type = EventType(data.get("event_type"))
    event_class = EVENT_REGISTRY.get(event_type, BaseEvent)
    return event_class(**data)
