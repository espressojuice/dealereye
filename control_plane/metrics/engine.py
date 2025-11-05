"""
Metrics computation engine for DealerEye.
Computes TTG, lobby occupancy, rack time, throughput from raw events.
"""
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict

from shared.schemas.events import (
    EventType, VehicleArrivalEvent, VehicleExitEvent,
    GreetStartedEvent, BayEntryEvent, BayExitEvent,
    LobbyEnterEvent, LobbyExitEvent
)
from shared.models.metrics import MetricName, WindowSize, MetricValue

logger = logging.getLogger(__name__)


class MetricsEngine:
    """
    Computes business metrics from domain events.
    Maintains sliding windows for real-time metric calculation.
    """

    def __init__(self):
        # Event buffers for metric computation
        self.arrivals_buffer: Dict[UUID, List[VehicleArrivalEvent]] = defaultdict(list)
        self.greets_buffer: Dict[UUID, List[GreetStartedEvent]] = defaultdict(list)
        self.bay_entries: Dict[UUID, Dict[str, BayEntryEvent]] = defaultdict(dict)
        self.lobby_counts: Dict[UUID, int] = defaultdict(int)

        # Configuration
        self.ttg_max_match_window = timedelta(minutes=5)
        self.buffer_retention = timedelta(hours=1)

    def process_event(self, event: dict) -> List[MetricValue]:
        """
        Process incoming event and generate metrics.
        Returns list of computed metrics.
        """
        event_type = event.get("event_type")
        metrics = []

        try:
            if event_type == EventType.VEHICLE_ARRIVAL:
                self._on_vehicle_arrival(event)

            elif event_type == EventType.GREET_STARTED:
                metric = self._on_greet_started(event)
                if metric:
                    metrics.append(metric)

            elif event_type == EventType.BAY_ENTRY:
                self._on_bay_entry(event)

            elif event_type == EventType.BAY_EXIT:
                metric = self._on_bay_exit(event)
                if metric:
                    metrics.append(metric)

            elif event_type == EventType.LOBBY_ENTER:
                self._on_lobby_enter(event)
                metrics.append(self._get_lobby_occupancy(event))

            elif event_type == EventType.LOBBY_EXIT:
                self._on_lobby_exit(event)
                metrics.append(self._get_lobby_occupancy(event))

        except Exception as e:
            logger.error(f"Error processing event for metrics: {e}", exc_info=True)

        return metrics

    def _on_vehicle_arrival(self, event: dict):
        """Buffer vehicle arrival for TTG calculation."""
        site_id = UUID(event["site_id"])
        self.arrivals_buffer[site_id].append(event)

        # Clean old arrivals
        cutoff = datetime.fromisoformat(event["timestamp"]) - self.buffer_retention
        self.arrivals_buffer[site_id] = [
            a for a in self.arrivals_buffer[site_id]
            if datetime.fromisoformat(a["timestamp"]) > cutoff
        ]

    def _on_greet_started(self, event: dict) -> Optional[MetricValue]:
        """
        Compute Time to Greet (TTG).
        Match greet event with nearest preceding vehicle arrival.
        """
        site_id = UUID(event["site_id"])
        greet_time = datetime.fromisoformat(event["timestamp"])
        vehicle_track = event["vehicle_track_id"]

        # Find matching arrival within window
        arrivals = self.arrivals_buffer[site_id]
        matched_arrival = None
        min_delta = None

        for arrival in arrivals:
            if arrival["track_id"] == vehicle_track:
                arrival_time = datetime.fromisoformat(arrival["timestamp"])
                delta = greet_time - arrival_time

                if timedelta(0) < delta < self.ttg_max_match_window:
                    if min_delta is None or delta < min_delta:
                        min_delta = delta
                        matched_arrival = arrival

        if matched_arrival:
            ttg_seconds = min_delta.total_seconds()
            logger.info(f"TTG computed: {ttg_seconds:.1f}s for site {site_id}")

            return MetricValue(
                metric_id=UUID(event["event_id"]),
                tenant_id=UUID(event["tenant_id"]),
                site_id=site_id,
                metric_name=MetricName.TIME_TO_GREET,
                window_start=greet_time,
                window_size=WindowSize.ONE_MINUTE,
                value=ttg_seconds,
                unit="seconds",
                dimensions={
                    "camera_id": event["camera_id"],
                    "zone_id": event["zone_id"],
                },
            )
        else:
            logger.warning(f"No matching arrival found for greet event {event['event_id']}")
            return None

    def _on_bay_entry(self, event: dict):
        """Buffer bay entry for rack time calculation."""
        site_id = UUID(event["site_id"])
        track_id = event["track_id"]
        self.bay_entries[site_id][track_id] = event

    def _on_bay_exit(self, event: dict) -> Optional[MetricValue]:
        """
        Compute rack time.
        Match bay exit with bay entry.
        """
        site_id = UUID(event["site_id"])
        track_id = event["track_id"]

        entry = self.bay_entries[site_id].get(track_id)
        if not entry:
            logger.warning(f"No bay entry found for track {track_id}")
            return None

        entry_time = datetime.fromisoformat(entry["timestamp"])
        exit_time = datetime.fromisoformat(event["timestamp"])
        rack_time_seconds = (exit_time - entry_time).total_seconds()

        # Clear entry
        del self.bay_entries[site_id][track_id]

        logger.info(f"Rack time computed: {rack_time_seconds:.1f}s for site {site_id}")

        return MetricValue(
            metric_id=UUID(event["event_id"]),
            tenant_id=UUID(event["tenant_id"]),
            site_id=site_id,
            metric_name=MetricName.RACK_TIME,
            window_start=exit_time,
            window_size=WindowSize.ONE_MINUTE,
            value=rack_time_seconds,
            unit="seconds",
            dimensions={
                "bay_id": event["bay_id"],
            },
            is_estimated=True,  # Mark as estimated until RO integration
        )

    def _on_lobby_enter(self, event: dict):
        """Increment lobby count."""
        site_id = UUID(event["site_id"])
        self.lobby_counts[site_id] += 1

    def _on_lobby_exit(self, event: dict):
        """Decrement lobby count."""
        site_id = UUID(event["site_id"])
        self.lobby_counts[site_id] = max(0, self.lobby_counts[site_id] - 1)

    def _get_lobby_occupancy(self, event: dict) -> MetricValue:
        """Get current lobby occupancy."""
        site_id = UUID(event["site_id"])
        count = self.lobby_counts[site_id]

        return MetricValue(
            metric_id=UUID(event["event_id"]),
            tenant_id=UUID(event["tenant_id"]),
            site_id=site_id,
            metric_name=MetricName.LOBBY_OCCUPANCY,
            window_start=datetime.fromisoformat(event["timestamp"]),
            window_size=WindowSize.ONE_MINUTE,
            value=float(count),
            unit="persons",
            dimensions={"door_id": event.get("door_id")},
        )

    def compute_throughput(self, site_id: UUID, start: datetime, end: datetime) -> int:
        """
        Compute drive throughput (unique arrivals in time window).
        """
        arrivals = self.arrivals_buffer[site_id]
        unique_tracks = set()

        for arrival in arrivals:
            arrival_time = datetime.fromisoformat(arrival["timestamp"])
            if start <= arrival_time <= end:
                unique_tracks.add(arrival["track_id"])

        return len(unique_tracks)
