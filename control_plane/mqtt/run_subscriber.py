"""
Standalone MQTT subscriber runner.
Consumes events from MQTT and stores them in the database.
"""
import asyncio
import logging
import signal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shared.config import ControlPlaneConfig
from control_plane.mqtt.subscriber import MQTTSubscriber
from control_plane.storage.crud import EventCRUD
from shared.schemas.events import deserialize_event, BaseEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SubscriberService:
    """MQTT Subscriber Service"""

    def __init__(self):
        self.config = ControlPlaneConfig()
        self.running = False

        # Database setup
        self.engine = create_engine(self.config.DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # MQTT subscriber
        self.subscriber = MQTTSubscriber(self.config, self.handle_event)

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def handle_event(self, event: BaseEvent):
        """
        Handle incoming event from MQTT.

        Args:
            event: Deserialized event object
        """
        try:
            # Extract tenant and site from event
            # The subscriber should add these as attributes
            tenant_id = getattr(event, 'tenant_id', None)
            site_id = getattr(event, 'site_id', None)

            if not tenant_id or not site_id:
                logger.warning(f"Event missing tenant_id or site_id: {event}")
                return

            # Store in database
            db = self.SessionLocal()
            try:
                crud = EventCRUD(db)
                db_event = crud.create_event(
                    tenant_id=str(tenant_id),
                    site_id=str(site_id),
                    event=event,
                )
                logger.info(f"Stored event: {event.event_type} for site {site_id}")
            except Exception as e:
                logger.error(f"Failed to store event: {e}", exc_info=True)
                db.rollback()
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)

    def run(self):
        """Run subscriber service."""
        logger.info("Starting MQTT Subscriber Service")
        logger.info(f"MQTT Broker: {self.config.MQTT_BROKER_HOST}:{self.config.MQTT_BROKER_PORT}")
        logger.info(f"Database: {self.config.DATABASE_URL}")

        try:
            # Connect to MQTT
            self.subscriber.connect()
            self.running = True

            logger.info("MQTT Subscriber running... Press Ctrl+C to stop")

            # Keep running
            while self.running:
                asyncio.run(asyncio.sleep(1))

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.subscriber.disconnect()
            logger.info("MQTT Subscriber stopped")


if __name__ == "__main__":
    service = SubscriberService()
    service.run()
