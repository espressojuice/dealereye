"""
Shared configuration utilities for DealerEye services.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


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

    # Offline queue configuration
    MAX_OFFLINE_QUEUE_SIZE: int = 10000
    OFFLINE_QUEUE_MAX_AGE_HOURS: int = 24

    # Health monitoring
    HEALTH_CHECK_INTERVAL_SECONDS: int = 30
    HEARTBEAT_INTERVAL_SECONDS: int = 60

    # Video processing
    PROCESS_INTERVAL_MS: int = 33
    MAX_FPS: int = 30

    model_config = ConfigDict(env_file=".env", extra="ignore")


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
    S3_ENDPOINT: Optional[str] = None
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "dealereye-clips"
    S3_REGION: str = "us-east-1"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    JWT_SECRET: str = "change-this-secret"
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
    TTG_MAX_MATCH_WINDOW_SECONDS: int = 300

    model_config = ConfigDict(env_file=".env", extra="ignore")


class DashboardConfig(BaseSettings):
    """Dashboard configuration."""
    API_BASE_URL: str = "http://localhost:8000"
    WS_BASE_URL: str = "ws://localhost:8000"

    model_config = ConfigDict(env_file=".env", extra="ignore")
