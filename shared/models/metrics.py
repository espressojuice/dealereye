"""
Metrics models for DealerEye analytics.
Time-series metrics with dimensions for drill-down.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class MetricName(str, Enum):
    """Core metrics computed from events."""
    TIME_TO_GREET = "time_to_greet"
    RACK_TIME = "rack_time"
    LOBBY_OCCUPANCY = "lobby_occupancy"
    OIL_CHANGE_CYCLE_TIME = "oil_change_cycle_time"
    DRIVE_THROUGHPUT = "drive_throughput"
    AVG_RACK_TIME_BY_TECH = "avg_rack_time_by_tech"
    AFTER_HOURS_CROSSINGS = "after_hours_crossings"


class WindowSize(str, Enum):
    """Time window aggregation sizes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1mo"


class MetricValue(BaseModel):
    """Single metric value with dimensions."""
    metric_id: UUID
    tenant_id: UUID
    site_id: UUID
    metric_name: MetricName
    window_start: datetime
    window_size: WindowSize
    value: float
    unit: str  # "seconds", "count", "persons", etc.
    dimensions: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"technician_id": "..."}
    is_estimated: bool = False  # Mark as estimated if no sensor data
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class MetricAggregation(BaseModel):
    """Aggregated metric over a time range."""
    metric_name: MetricName
    tenant_id: UUID
    site_id: UUID
    start_time: datetime
    end_time: datetime
    count: int
    mean: float
    median: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    min: float
    max: float
    unit: str
    dimensions: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class YoYComparison(BaseModel):
    """Year-over-year comparison with matched weekdays."""
    metric_name: MetricName
    current_value: float
    prior_year_value: float
    delta: float
    delta_pct: float
    unit: str
    current_start: datetime
    current_end: datetime
    prior_start: datetime
    prior_end: datetime
