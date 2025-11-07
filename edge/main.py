"""
Edge device main application.
Integrates DeepStream pipeline, analytics engine, and MQTT uplink.
"""
import logging
import signal
import sys
import time
from typing import Dict, Optional
from pathlib import Path
from uuid import UUID

from shared.config import EdgeConfig
from edge.analytics.zone_line_engine import ZoneLineEngine
from edge.uplink.mqtt_client import MQTTUplink
from edge.health.monitor import HealthMonitor
from edge.video.opencv_processor import OpenCVVideoProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class EdgeApplication:
    """
    Main edge application orchestrator.
    Manages DeepStream pipeline, analytics, and uplink.
    """

    def __init__(self):
        # Load configuration
        self.config = EdgeConfig()

        # Initialize components
        self.mqtt_client = MQTTUplink(self.config)
        self.health_monitor = HealthMonitor(self.config, self.mqtt_client)

        # Analytics engines per camera
        self.zone_line_engines: Dict[str, ZoneLineEngine] = {}

        # Video processor
        self.video_processor: Optional[OpenCVVideoProcessor] = None

        # Graceful shutdown
        self.running = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def initialize_cameras(self):
        """
        Initialize camera streams and analytics engines.
        In production, this loads camera configs from local cache or control plane.
        """
        # TODO: Load camera configurations from control plane via MQTT or REST
        # For now, create placeholder analytics engines
        logger.info("Initializing camera analytics engines...")

        # Example: Create analytics engine for each camera
        # In production, this is populated from control plane
        example_camera_id = UUID(self.config.SITE_ID)  # Placeholder
        engine = ZoneLineEngine(
            tenant_id=UUID(self.config.TENANT_ID),
            site_id=UUID(self.config.SITE_ID),
            camera_id=example_camera_id,
        )
        self.zone_line_engines[str(example_camera_id)] = engine

    def start_video_processor(self):
        """
        Start video processor with OpenCV and YOLO.
        """
        logger.info("Starting video processor...")

        # Use test video file for now
        # TODO: Load camera RTSP URLs from control plane config
        test_video = "/opt/dealereye/test_videos/car-detection.mp4"
        model_path = "/opt/dealereye/models/yolov8n.pt"

        # Create video processor
        self.video_processor = OpenCVVideoProcessor(
            source=test_video,
            model_path=model_path,
            conf_threshold=0.25,
            iou_threshold=0.45,
            enable_tracking=True,  # Enabled after scipy upgrade
        )

        # Initialize processor
        self.video_processor.initialize()

        # Register callback for detections
        self.video_processor.set_detection_callback(self._on_detection)

        logger.info("Video processor initialized")

    def _on_detection(self, frame_num: int, detections: list):
        """
        Callback for processing detections from DeepStream pipeline.
        Converts raw YOLO detections to business events.

        Args:
            frame_num: Frame number
            detections: List of detection dicts with bbox, class_id, confidence, object_id
        """
        # Filter for vehicles and people only (class_id 0=person, 2=car, 5=bus, 7=truck)
        vehicle_classes = {0, 2, 5, 7}

        for det in detections:
            class_id = det["class_id"]

            if class_id not in vehicle_classes:
                continue

            # Log detection
            object_class = "person" if class_id == 0 else "vehicle"
            logger.debug(
                f"Frame {frame_num}: Detected {object_class} "
                f"(ID: {det['object_id']}, conf: {det['confidence']:.2f})"
            )

            # TODO: Convert to zone entry/exit and line crossing events
            # For now, just count detections
            if frame_num % 30 == 0:  # Log every 30 frames (~1 second)
                logger.info(
                    f"Frame {frame_num}: Active detections: {len(detections)}"
                )

    def process_deepstream_event(self, ds_event: dict):
        """
        Process event from DeepStream analytics.
        Converts DeepStream metadata to domain events.
        """
        camera_id = ds_event.get("camera_id")
        event_type = ds_event.get("event_type")

        engine = self.zone_line_engines.get(camera_id)
        if not engine:
            logger.warning(f"No analytics engine for camera {camera_id}")
            return

        try:
            # Process different event types
            if event_type == "line_crossing":
                domain_event = engine.on_line_crossing(
                    track_id=ds_event["track_id"],
                    line_id=UUID(ds_event["line_id"]),
                    direction=ds_event["direction"],
                    confidence=ds_event["confidence"],
                    object_class=ds_event["object_class"],
                )
                if domain_event:
                    self.mqtt_client.publish_event(domain_event)

            elif event_type == "zone_entry":
                engine.on_zone_entry(
                    track_id=ds_event["track_id"],
                    zone_id=UUID(ds_event["zone_id"]),
                    object_class=ds_event["object_class"],
                )

            elif event_type == "zone_exit":
                engine.on_zone_exit(
                    track_id=ds_event["track_id"],
                    zone_id=UUID(ds_event["zone_id"]),
                )

        except Exception as e:
            logger.error(f"Error processing DeepStream event: {e}", exc_info=True)

    def analytics_loop(self):
        """
        Periodic analytics checks.
        Runs dwell detection and greet proximity checks.
        """
        while self.running:
            try:
                for engine in self.zone_line_engines.values():
                    # Check dwell events
                    dwell_events = engine.check_dwell_events()
                    for event in dwell_events:
                        self.mqtt_client.publish_event(event)

                    # Check greet proximity
                    greet_events = engine.check_greet_proximity()
                    for event in greet_events:
                        self.mqtt_client.publish_event(event)

                    # Cleanup stale tracks
                    engine.cleanup_stale_tracks()

                time.sleep(1)  # Run every second

            except Exception as e:
                logger.error(f"Error in analytics loop: {e}", exc_info=True)

    def run(self):
        """Main application loop."""
        logger.info("Starting DealerEye Edge Application")
        logger.info(f"Edge ID: {self.config.EDGE_ID}")
        logger.info(f"Site ID: {self.config.SITE_ID}")

        try:
            # Connect to MQTT broker
            self.mqtt_client.connect()

            # Initialize cameras
            self.initialize_cameras()

            # Start video processor
            self.start_video_processor()

            # Start health monitoring
            self.health_monitor.start()

            # Start video processing (blocks until complete or interrupted)
            self.running = True
            if self.video_processor:
                self.video_processor.run()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.shutdown()

    def shutdown(self):
        """Clean shutdown."""
        logger.info("Shutting down edge application...")

        # Stop video processor
        if self.video_processor:
            self.video_processor.stop()

        # Stop health monitor
        if hasattr(self, "health_monitor"):
            self.health_monitor.stop()

        # Disconnect MQTT
        if hasattr(self, "mqtt_client"):
            self.mqtt_client.disconnect()

        logger.info("Edge application shutdown complete")


if __name__ == "__main__":
    app = EdgeApplication()
    app.run()
