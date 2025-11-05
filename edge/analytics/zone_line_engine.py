"""
Zone and line crossing analytics engine.
Processes DeepStream NvDsAnalytics events and generates domain events.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
import numpy as np

from shared.schemas.events import (
    VehicleArrivalEvent,
    VehicleExitEvent,
    GreetStartedEvent,
    BayEntryEvent,
    BayExitEvent,
    LobbyEnterEvent,
    LobbyExitEvent,
    ZoneDwellEvent,
    LineCrossingEvent,
    ObjectClass,
)
from shared.models.core import Zone, Line, LineType, ZoneType


@dataclass
class TrackedObject:
    """Tracked object state."""
    track_id: str
    object_class: ObjectClass
    first_seen: datetime
    last_seen: datetime
    zone_entry_times: Dict[UUID, datetime]  # zone_id -> entry time
    lines_crossed: List[UUID]  # line_ids


class ZoneLineEngine:
    """
    Manages zone and line crossing detection.
    Maintains tracked object state for dwell and proximity calculations.
    """

    def __init__(self, tenant_id: UUID, site_id: UUID, camera_id: UUID):
        self.tenant_id = tenant_id
        self.site_id = site_id
        self.camera_id = camera_id

        # Configuration loaded from control plane
        self.zones: Dict[UUID, Zone] = {}
        self.lines: Dict[UUID, Line] = {}

        # Tracking state
        self.tracked_objects: Dict[str, TrackedObject] = {}

        # Dwell thresholds (seconds)
        self.default_dwell_threshold = 2.0

    def load_zones(self, zones: List[Zone]):
        """Load zone configurations."""
        self.zones = {zone.zone_id: zone for zone in zones}

    def load_lines(self, lines: List[Line]):
        """Load line configurations."""
        self.lines = {line.line_id: line for line in lines}

    def update_tracking(self, track_id: str, object_class: ObjectClass):
        """Update tracked object state."""
        now = datetime.utcnow()
        if track_id not in self.tracked_objects:
            self.tracked_objects[track_id] = TrackedObject(
                track_id=track_id,
                object_class=object_class,
                first_seen=now,
                last_seen=now,
                zone_entry_times={},
                lines_crossed=[],
            )
        else:
            self.tracked_objects[track_id].last_seen = now

    def on_line_crossing(
        self,
        track_id: str,
        line_id: UUID,
        direction: str,
        confidence: float,
        object_class: ObjectClass,
    ) -> Optional[LineCrossingEvent]:
        """Process line crossing from DeepStream analytics."""
        self.update_tracking(track_id, object_class)

        line = self.lines.get(line_id)
        if not line:
            return None

        # Generate specific event based on line semantics
        if line.line_type == LineType.ENTRY:
            return VehicleArrivalEvent(
                tenant_id=self.tenant_id,
                site_id=self.site_id,
                camera_id=self.camera_id,
                track_id=track_id,
                line_id=line_id,
                confidence=confidence,
            )
        elif line.line_type == LineType.EXIT:
            return VehicleExitEvent(
                tenant_id=self.tenant_id,
                site_id=self.site_id,
                camera_id=self.camera_id,
                track_id=track_id,
                line_id=line_id,
                confidence=confidence,
            )
        elif line.line_type == LineType.BAY_ENTRY:
            return BayEntryEvent(
                tenant_id=self.tenant_id,
                site_id=self.site_id,
                camera_id=self.camera_id,
                track_id=track_id,
                bay_id=line_id,  # Using line_id as bay_id
                confidence=confidence,
            )
        elif line.line_type == LineType.BAY_EXIT:
            return BayExitEvent(
                tenant_id=self.tenant_id,
                site_id=self.site_id,
                camera_id=self.camera_id,
                track_id=track_id,
                bay_id=line_id,
                confidence=confidence,
            )
        elif line.line_type == LineType.DOOR and object_class == ObjectClass.PERSON:
            if direction == "forward":
                return LobbyEnterEvent(
                    tenant_id=self.tenant_id,
                    site_id=self.site_id,
                    camera_id=self.camera_id,
                    track_id=track_id,
                    door_id=line_id,
                    confidence=confidence,
                )
            else:
                return LobbyExitEvent(
                    tenant_id=self.tenant_id,
                    site_id=self.site_id,
                    camera_id=self.camera_id,
                    track_id=track_id,
                    door_id=line_id,
                    confidence=confidence,
                )
        else:
            # Generic line crossing
            return LineCrossingEvent(
                tenant_id=self.tenant_id,
                site_id=self.site_id,
                camera_id=self.camera_id,
                track_id=track_id,
                object_class=object_class,
                line_id=line_id,
                direction=direction,
                confidence=confidence,
            )

    def on_zone_entry(
        self, track_id: str, zone_id: UUID, object_class: ObjectClass
    ):
        """Track object entry into zone."""
        self.update_tracking(track_id, object_class)
        obj = self.tracked_objects[track_id]
        if zone_id not in obj.zone_entry_times:
            obj.zone_entry_times[zone_id] = datetime.utcnow()

    def on_zone_exit(self, track_id: str, zone_id: UUID):
        """Track object exit from zone."""
        if track_id in self.tracked_objects:
            obj = self.tracked_objects[track_id]
            obj.zone_entry_times.pop(zone_id, None)

    def check_dwell_events(self) -> List[ZoneDwellEvent]:
        """Check for objects that have exceeded dwell threshold."""
        events = []
        now = datetime.utcnow()

        for track_id, obj in self.tracked_objects.items():
            for zone_id, entry_time in obj.zone_entry_times.items():
                zone = self.zones.get(zone_id)
                if not zone:
                    continue

                dwell_threshold = (
                    zone.dwell_threshold_seconds or self.default_dwell_threshold
                )
                dwell_seconds = (now - entry_time).total_seconds()

                if dwell_seconds >= dwell_threshold:
                    events.append(
                        ZoneDwellEvent(
                            tenant_id=self.tenant_id,
                            site_id=self.site_id,
                            camera_id=self.camera_id,
                            track_id=track_id,
                            object_class=obj.object_class,
                            zone_id=zone_id,
                            dwell_seconds=dwell_seconds,
                            confidence=0.9,  # High confidence for dwell
                        )
                    )

                    # Reset entry time to avoid duplicate events
                    obj.zone_entry_times[zone_id] = now

        return events

    def check_greet_proximity(self) -> List[GreetStartedEvent]:
        """
        Check for person-vehicle proximity in greet zones.
        Generates GreetStartedEvent when person and vehicle are both in greet zone.
        """
        events = []

        # Find all greet zones
        greet_zones = [
            z for z in self.zones.values() if z.zone_type == ZoneType.GREET_ZONE
        ]

        for zone in greet_zones:
            # Get all objects currently in this zone
            vehicles_in_zone = []
            persons_in_zone = []

            for track_id, obj in self.tracked_objects.items():
                if zone.zone_id in obj.zone_entry_times:
                    if obj.object_class == ObjectClass.VEHICLE:
                        vehicles_in_zone.append(obj)
                    elif obj.object_class == ObjectClass.PERSON:
                        persons_in_zone.append(obj)

            # Generate greet events for each vehicle-person pair
            for vehicle in vehicles_in_zone:
                for person in persons_in_zone:
                    # Check if both have been in zone long enough
                    vehicle_dwell = (
                        datetime.utcnow() - vehicle.zone_entry_times[zone.zone_id]
                    ).total_seconds()
                    person_dwell = (
                        datetime.utcnow() - person.zone_entry_times[zone.zone_id]
                    ).total_seconds()

                    min_dwell = min(vehicle_dwell, person_dwell)
                    if min_dwell >= 1.0:  # Both present for at least 1 second
                        events.append(
                            GreetStartedEvent(
                                tenant_id=self.tenant_id,
                                site_id=self.site_id,
                                camera_id=self.camera_id,
                                vehicle_track_id=vehicle.track_id,
                                person_track_id=person.track_id,
                                zone_id=zone.zone_id,
                                proximity_seconds=min_dwell,
                                confidence=0.85,
                            )
                        )

        return events

    def cleanup_stale_tracks(self, max_age_seconds: int = 60):
        """Remove tracked objects that haven't been seen recently."""
        now = datetime.utcnow()
        stale_tracks = [
            track_id
            for track_id, obj in self.tracked_objects.items()
            if (now - obj.last_seen).total_seconds() > max_age_seconds
        ]
        for track_id in stale_tracks:
            del self.tracked_objects[track_id]
