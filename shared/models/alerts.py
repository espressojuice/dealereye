"""
Alert models for DealerEye notification system.
Rules engine with cooldown and acknowledgement.
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert lifecycle status."""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    AUTO_RESOLVED = "auto_resolved"


class AlertType(str, Enum):
    """Alert type categories."""
    SERVICE = "service"  # Service operations (TTG, wait times)
    SECURITY = "security"  # After-hours, perimeter
    MAINTENANCE = "maintenance"  # Equipment, system health
    OCCUPANCY = "occupancy"  # Lobby overcrowding
    CUSTOM = "custom"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    WEBHOOK = "webhook"


class RuleConditionOperator(str, Enum):
    """Operators for rule conditions."""
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_OR_EQUAL = "gte"
    LESS_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"


class RuleCondition(BaseModel):
    """Single condition in an alert rule."""
    field: str  # e.g., "ttg_seconds", "lobby_count", "after_hours"
    operator: RuleConditionOperator
    value: Any

    class Config:
        use_enum_values = True


class TimeWindow(BaseModel):
    """Time window when rule is active."""
    start_time: str  # "08:00"
    end_time: str  # "18:00"
    days_of_week: List[int] = Field(default=[0, 1, 2, 3, 4, 5])  # 0=Monday


class AlertRule(BaseModel):
    """Alert rule definition with conditions."""
    rule_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    site_id: Optional[UUID] = None  # None = applies to all sites in tenant
    name: str
    description: Optional[str] = None
    alert_type: AlertType
    severity: AlertSeverity
    conditions: List[RuleCondition]
    time_windows: List[TimeWindow] = Field(default_factory=list)  # Empty = always active
    cooldown_seconds: int = 300  # 5 minutes default
    channels: List[NotificationChannel]
    recipients: List[str]  # Email addresses or phone numbers
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True

    def is_active_now(self, dt: datetime) -> bool:
        """Check if rule is active at given datetime."""
        if not self.enabled:
            return False
        if not self.time_windows:
            return True

        for window in self.time_windows:
            if dt.weekday() in window.days_of_week:
                # Simple time check (doesn't handle overnight windows)
                current_time = dt.time().strftime("%H:%M")
                if window.start_time <= current_time <= window.end_time:
                    return True
        return False


class DeliveryResult(BaseModel):
    """Result of notification delivery attempt."""
    channel: NotificationChannel
    recipient: str
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    class Config:
        use_enum_values = True


class Alert(BaseModel):
    """Alert instance triggered by a rule."""
    alert_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    site_id: UUID
    rule_id: UUID
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    status: AlertStatus = AlertStatus.OPEN
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None  # user_id
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    context: Dict[str, Any] = Field(default_factory=dict)  # Related event data
    clip_url: Optional[str] = None
    keyframe_url: Optional[str] = None
    delivery_results: List[DeliveryResult] = Field(default_factory=list)

    class Config:
        use_enum_values = True

    def acknowledge(self, user_id: UUID):
        """Acknowledge this alert."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = user_id

    def resolve(self, user_id: UUID):
        """Manually resolve this alert."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        self.resolved_by = user_id

    def auto_resolve(self):
        """Auto-resolve this alert."""
        self.status = AlertStatus.AUTO_RESOLVED
        self.resolved_at = datetime.utcnow()


class AlertAuditLog(BaseModel):
    """Audit trail for alert actions."""
    log_id: UUID = Field(default_factory=uuid4)
    alert_id: UUID
    user_id: Optional[UUID] = None  # None for system actions
    action: str  # "created", "acknowledged", "resolved", "escalated"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
