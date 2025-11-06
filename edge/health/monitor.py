"""
Health monitoring for edge device.
Collects GPU, FPS, and system metrics for heartbeat events.
"""
import logging
import threading
import time
import psutil
from typing import Optional

from shared.config import EdgeConfig
from shared.schemas.events import SystemHeartbeatEvent

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors edge device health and publishes heartbeat events.
    """

    def __init__(self, config: EdgeConfig, mqtt_client):
        self.config = config
        self.mqtt_client = mqtt_client

        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Metrics
        self.fps_samples = []
        self.dropped_frames_samples = []
        self.start_time = time.time()

    def start(self):
        """Start health monitoring thread."""
        if self.running:
            logger.warning("Health monitor already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Health monitor started")

    def stop(self):
        """Stop health monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Health monitor stopped")

    def record_fps(self, fps: float):
        """Record FPS sample."""
        self.fps_samples.append(fps)
        # Keep last 30 samples
        if len(self.fps_samples) > 30:
            self.fps_samples.pop(0)

    def record_dropped_frames(self, dropped_pct: float):
        """Record dropped frames percentage."""
        self.dropped_frames_samples.append(dropped_pct)
        if len(self.dropped_frames_samples) > 30:
            self.dropped_frames_samples.pop(0)

    def _get_gpu_utilization(self) -> Optional[float]:
        """
        Get GPU utilization percentage.
        Uses nvidia-smi or pynvml if available.
        """
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            pynvml.nvmlShutdown()
            return float(utilization.gpu)
        except Exception as e:
            logger.debug(f"Failed to get GPU utilization: {e}")
            return None

    def _get_memory_usage(self) -> int:
        """Get memory usage in MB."""
        process = psutil.Process()
        return int(process.memory_info().rss / 1024 / 1024)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Calculate average metrics
                avg_fps = sum(self.fps_samples) / len(self.fps_samples) if self.fps_samples else 0.0
                avg_dropped = (
                    sum(self.dropped_frames_samples) / len(self.dropped_frames_samples)
                    if self.dropped_frames_samples
                    else 0.0
                )

                # Collect system metrics
                uptime_seconds = int(time.time() - self.start_time)
                gpu_util = self._get_gpu_utilization()
                memory_mb = self._get_memory_usage()

                # Create heartbeat event
                # Use null UUID for system-level heartbeat (not associated with specific camera)
                from uuid import UUID
                NULL_UUID = UUID('00000000-0000-0000-0000-000000000000')
                heartbeat = SystemHeartbeatEvent(
                    tenant_id=UUID(self.config.TENANT_ID),
                    site_id=UUID(self.config.SITE_ID),
                    camera_id=NULL_UUID,  # System-level heartbeat
                    fps=avg_fps,
                    dropped_frames_pct=avg_dropped,
                    edge_uptime_seconds=uptime_seconds,
                    gpu_utilization_pct=gpu_util,
                    memory_used_mb=memory_mb,
                )

                # Publish heartbeat
                self.mqtt_client.publish_event(heartbeat)

                # Also publish simple heartbeat status
                heartbeat_data = {
                    "fps": avg_fps,
                    "dropped_frames_pct": avg_dropped,
                    "uptime_seconds": uptime_seconds,
                    "gpu_utilization_pct": gpu_util,
                    "memory_mb": memory_mb,
                    "queue_size": self.mqtt_client.get_queue_size(),
                }
                self.mqtt_client.publish_heartbeat(heartbeat_data)

                logger.debug(f"Heartbeat: FPS={avg_fps:.1f}, Dropped={avg_dropped:.2f}%, Uptime={uptime_seconds}s")

                # Sleep until next heartbeat
                time.sleep(self.config.HEARTBEAT_INTERVAL_SECONDS)

            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}", exc_info=True)
                time.sleep(10)  # Back off on error
