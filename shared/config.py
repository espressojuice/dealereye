"""
Shared configuration utilities for DealerEye services.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class EdgeConfig(BaseSettings):
    """Edge device configuration."""
    # Device identity
    EDGE_ID: str
    SITE_ID: str
    TENANT_ID: str

    # MQTT broker
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    MQTT_QOS: int = 1
    MQTT_KEEPALIVE: int = 60

    # DeepStream
    DEEPSTREAM_CONFIG_PATH: str = "/app/deepstream/config.txt"
    YOLO_ENGINE_PATH: str = "/app/models/yolo.engine"
    BYTETRACK_CONFIG_PATH: str = "/app/bytetrack/config.yaml"

    # Video processing
    BATCH_SIZE: int = 4
    TARGET_FPS: int = 15
    CONFIDENCE_THRESHOLD: float = 0.5
    NMS_THRESHOLD: float = 0.45

    # Buffering
    CLIP_PRE_ROLL_SECONDS: int = 5
    CLIP_POST_ROLL_SECONDS: int = 10
    MAX_RING_BUFFER_SECONDS: int = 60

    # Health
    HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Offline mode
    MAX_OFFLINE_QUEUE_SIZE: int = 10000
    OFFLINE_RETENTION_HOURS: int = 24

    class Config:
        env_file = ".env"
        case_sensitive = True


class ControlPlaneConfig(BaseSettings):
    """Control plane service configuration."""
    # Database
    DATABASE_URL: str = "postgresql://dealereye:password@localhost:5432/dealereye"
    REDIS_URL: str = "redis://localhost:6379/0"

    # MQTT broker
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None

    # Object storage
    S3_ENDPOINT: Optional[str] = None  # None = AWS S3
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str = "dealereye-clips"
    S3_REGION: str = "us-east-1"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Notifications
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None

    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    # Metrics computation
    METRICS_COMPUTE_INTERVAL_SECONDS: int = 60
    TTG_MAX_MATCH_WINDOW_SECONDS: int = 300  # 5 minutes

    class Config:
        env_file = ".env"
        case_sensitive = True


class DashboardConfig(BaseSettings):
    """Dashboard configuration."""
    API_BASE_URL: str = "http://localhost:8000"
    WS_BASE_URL: str = "ws://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = True
