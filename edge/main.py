"""
Edge device main application.
Integrates DeepStream pipeline, analytics engine, and MQTT uplink.
"""
import cv2
import logging
import signal
import sys
import time
from typing import Dict, Optional
from pathlib import Path
from uuid import UUID

from shared.config import EdgeConfig
from shared.camera_manager import CameraManager
from edge.analytics.zone_line_engine import ZoneLineEngine
from edge.uplink.mqtt_client import MQTTUplink
from edge.health.monitor import HealthMonitor
from edge.video.opencv_processor import OpenCVVideoProcessor
from edge.video.stream_server import MJPEGStreamServer

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

        # Initialize camera manager
        self.camera_manager = CameraManager()

        # Initialize components
        self.mqtt_client = MQTTUplink(self.config)
        self.health_monitor = HealthMonitor(self.config, self.mqtt_client)

        # Analytics engines per camera
        self.zone_line_engines: Dict[str, ZoneLineEngine] = {}

        # Video processor
        self.video_processor: Optional[OpenCVVideoProcessor] = None

        # MJPEG stream server for live viewing
        self.stream_server: Optional[MJPEGStreamServer] = None

        # Currently active camera
        self.active_camera: Optional[Dict] = None

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
        Loads camera configurations from camera manager.
        """
        logger.info("Loading camera configurations from camera manager...")

        # Load cameras from camera manager
        cameras = self.camera_manager.list_cameras()

        if not cameras:
            logger.warning("No cameras configured in camera manager")
            return

        logger.info(f"Found {len(cameras)} camera(s) in configuration")

        # Create analytics engines for each enabled camera
        for camera in cameras:
            if not camera.get('enabled', True):
                logger.info(f"Skipping disabled camera: {camera.get('name', camera['id'])}")
                continue

            camera_id = UUID(camera['id'])
            logger.info(f"Initializing analytics engine for camera: {camera.get('name', camera['id'])}")

            engine = ZoneLineEngine(
                tenant_id=UUID(self.config.TENANT_ID),
                site_id=UUID(self.config.SITE_ID),
                camera_id=camera_id,
            )
            self.zone_line_engines[str(camera_id)] = engine

            # Set first enabled camera as active
            if self.active_camera is None:
                self.active_camera = camera
                logger.info(f"Set active camera: {camera.get('name', camera['id'])}")

    def start_video_processor(self):
        """
        Start video processor with OpenCV and YOLO.
        """
        logger.info("Starting video processor...")

        # Check if we have an active camera configured
        if not self.active_camera:
            logger.error("No active camera configured. Cannot start video processor.")
            return

        # Get camera configuration from active camera
        rtsp_url = self.active_camera['rtsp_url']
        camera_name = self.active_camera.get('name', self.active_camera['id'])
        logger.info(f"Starting video processor for camera: {camera_name}")
        logger.info(f"RTSP URL: {rtsp_url}")

        model_path = "/opt/dealereye/models/yolov8n.engine"

        # Create and start MJPEG stream server
        logger.info("Starting MJPEG stream server...")
        self.stream_server = MJPEGStreamServer(host="0.0.0.0", port=8080)
        self.stream_server.start()

        # Create video processor with stream server
        self.video_processor = OpenCVVideoProcessor(
            source=rtsp_url,
            model_path=model_path,
            conf_threshold=0.25,
            iou_threshold=0.45,
            enable_tracking=True,  # Enabled after scipy upgrade
            stream_server=self.stream_server,
        )

        # Initialize processor
        self.video_processor.initialize()

        # Register callback for detections
        self.video_processor.set_detection_callback(self._on_detection)

        # Extract camera IP from RTSP URL for display purposes
        # Format: rtsp://user:pass@ip:port/path
        import re
        camera_ip = "Unknown"
        ip_match = re.search(r'@([^:]+):', rtsp_url)
        if ip_match:
            camera_ip = ip_match.group(1)

        # Get resolution from video capture
        width = int(self.video_processor.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.video_processor.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        resolution = f"{width}x{height}"

        # Get model name from processor
        model_name = "GPU Accelerated YOLO Detection"

        # Update stream server stats
        self.stream_server.update_stats(
            camera_ip=camera_ip,
            resolution=resolution,
            fps="0.0",  # Will be updated during processing
            model=model_name
        )

        logger.info(f"Video processor initialized for {camera_name} ({camera_ip}) at {resolution}")

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

        # Stop stream server
        if self.stream_server:
            self.stream_server.stop()

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
