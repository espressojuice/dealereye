"""
MQTT subscriber for control plane.
Receives events from edge devices and processes them.
"""
import json
import logging
from typing import Callable
import paho.mqtt.client as mqtt

from shared.config import ControlPlaneConfig
from shared.schemas.events import deserialize_event

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    """
    MQTT subscriber for event ingestion from edge devices.
    Routes events to metrics engine and storage.
    """

    def __init__(self, config: ControlPlaneConfig, event_handler: Callable):
        self.config = config
        self.event_handler = event_handler
        self.client = mqtt.Client(client_id="control-plane", clean_session=False)

        # Callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # Authentication
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

    def connect(self):
        """Connect to MQTT broker and subscribe to topics."""
        try:
            self.client.connect(
                self.config.MQTT_BROKER_HOST,
                self.config.MQTT_BROKER_PORT,
                keepalive=60,
            )
            self.client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.config.MQTT_BROKER_HOST}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            logger.info("Successfully connected to MQTT broker")

            # Subscribe to all event topics
            # Topic pattern: dealereye/+/+/events
            client.subscribe("dealereye/+/+/events", qos=1)
            client.subscribe("dealereye/+/+/heartbeat", qos=1)

            logger.info("Subscribed to event topics")
        else:
            logger.error(f"Failed to connect with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        if rc != 0:
            logger.warning(f"Unexpected disconnect (code {rc}). Will auto-reconnect.")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) >= 4:
                tenant_id = topic_parts[1]
                site_id = topic_parts[2]
                message_type = topic_parts[3]

                payload = json.loads(msg.payload.decode())

                if message_type == "events":
                    # Parse domain event
                    event = deserialize_event(payload)
                    logger.debug(f"Received event: {event.event_type} from site {site_id}")

                    # Add tenant and site context to event
                    event.tenant_id = tenant_id
                    event.site_id = site_id

                    # Pass to event handler
                    self.event_handler(event)

                elif message_type == "heartbeat":
                    logger.debug(f"Received heartbeat from site {site_id}")
                    # TODO: Update camera health status

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}", exc_info=True)
