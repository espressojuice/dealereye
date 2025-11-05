"""
MQTT client for event uplink from edge to control plane.
Reliable delivery with QoS 1, offline queueing, and automatic reconnection.
"""
import json
import queue
import logging
from typing import Optional, Callable
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

from shared.schemas.events import BaseEvent
from shared.config import EdgeConfig

logger = logging.getLogger(__name__)


class MQTTUplink:
    """
    MQTT client for publishing events to control plane.
    Features:
    - QoS 1 for at-least-once delivery
    - Persistent offline queue
    - Automatic reconnection
    - Event serialization
    """

    def __init__(self, config: EdgeConfig):
        self.config = config
        self.client = mqtt.Client(client_id=f"edge-{config.EDGE_ID}", clean_session=False)

        # Offline message queue
        self.offline_queue: queue.Queue = queue.Queue(maxsize=config.MAX_OFFLINE_QUEUE_SIZE)
        self.is_connected = False

        # Topic structure: dealereye/{tenant_id}/{site_id}/events
        self.event_topic = f"dealereye/{config.TENANT_ID}/{config.SITE_ID}/events"
        self.heartbeat_topic = f"dealereye/{config.TENANT_ID}/{config.SITE_ID}/heartbeat"

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

        # Authentication
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

        # Will message for disconnect detection
        will_payload = json.dumps({
            "edge_id": config.EDGE_ID,
            "site_id": config.SITE_ID,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "disconnected"
        })
        self.client.will_set(
            self.heartbeat_topic,
            payload=will_payload,
            qos=1,
            retain=True
        )

    def connect(self):
        """Connect to MQTT broker with automatic reconnection."""
        try:
            self.client.connect(
                self.config.MQTT_BROKER_HOST,
                self.config.MQTT_BROKER_PORT,
                keepalive=self.config.MQTT_KEEPALIVE,
            )
            self.client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.config.MQTT_BROKER_HOST}:{self.config.MQTT_BROKER_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Gracefully disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            self.is_connected = True
            logger.info("Successfully connected to MQTT broker")
            # Flush offline queue
            self._flush_offline_queue()
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            self.is_connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnect from MQTT broker (code {rc}). Will auto-reconnect.")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_publish(self, client, userdata, mid):
        """Callback when message is published."""
        logger.debug(f"Message {mid} published successfully")

    def publish_event(self, event: BaseEvent) -> bool:
        """
        Publish event to control plane.
        Returns True if published immediately, False if queued for later.
        """
        payload = event.model_dump_json()

        if self.is_connected:
            try:
                result = self.client.publish(
                    self.event_topic,
                    payload=payload,
                    qos=self.config.MQTT_QOS,
                    retain=False,
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Published event {event.event_type} with id {event.event_id}")
                    return True
                else:
                    logger.warning(f"Failed to publish event: {result.rc}")
                    self._queue_offline(payload)
                    return False
            except Exception as e:
                logger.error(f"Error publishing event: {e}")
                self._queue_offline(payload)
                return False
        else:
            # Queue for later delivery
            self._queue_offline(payload)
            return False

    def publish_heartbeat(self, heartbeat_data: dict):
        """Publish system heartbeat."""
        heartbeat_data["edge_id"] = self.config.EDGE_ID
        heartbeat_data["site_id"] = self.config.SITE_ID
        heartbeat_data["timestamp"] = datetime.utcnow().isoformat()

        payload = json.dumps(heartbeat_data)

        if self.is_connected:
            self.client.publish(
                self.heartbeat_topic,
                payload=payload,
                qos=self.config.MQTT_QOS,
                retain=True,  # Retain heartbeat for last-known status
            )

    def _queue_offline(self, payload: str):
        """Queue message for offline delivery."""
        try:
            self.offline_queue.put_nowait(payload)
            logger.info(f"Queued event for offline delivery. Queue size: {self.offline_queue.qsize()}")
        except queue.Full:
            logger.error("Offline queue is full! Dropping event.")

    def _flush_offline_queue(self):
        """Flush offline queue when reconnected."""
        if self.offline_queue.empty():
            return

        logger.info(f"Flushing {self.offline_queue.qsize()} queued events")
        flushed = 0

        while not self.offline_queue.empty():
            try:
                payload = self.offline_queue.get_nowait()
                result = self.client.publish(
                    self.event_topic,
                    payload=payload,
                    qos=self.config.MQTT_QOS,
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    flushed += 1
                else:
                    # Put back in queue if failed
                    self.offline_queue.put_nowait(payload)
                    break
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error flushing offline queue: {e}")
                break

        logger.info(f"Flushed {flushed} events from offline queue")

    def get_queue_size(self) -> int:
        """Get current offline queue size."""
        return self.offline_queue.qsize()
