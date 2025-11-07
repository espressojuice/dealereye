"""
OpenCV-based video processor with YOLO inference and tracking.
Alternative to DeepStream when TensorRT compatibility issues exist.
"""
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Dict, List
import cv2
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class OpenCVVideoProcessor:
    """
    Video processor using OpenCV and Ultralytics YOLO.
    Supports file sources and RTSP streams with object tracking.
    """

    def __init__(
        self,
        source: str,
        model_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        enable_tracking: bool = True,
    ):
        """
        Initialize video processor.

        Args:
            source: Video file path or RTSP URL
            model_path: Path to YOLO model (.pt or .onnx)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
            enable_tracking: Enable object tracking
        """
        self.source = source
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.enable_tracking = enable_tracking

        self.model: Optional[YOLO] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.running = False
        self.detection_callback: Optional[Callable] = None

        self.frame_count = 0
        self.fps = 0

    def initialize(self):
        """Initialize model and video capture."""
        logger.info(f"Loading YOLO model from {self.model_path}...")

        # Load YOLO model
        self.model = YOLO(self.model_path)
        logger.info(f"Model loaded: {self.model.model_name}")

        # Open video source
        logger.info(f"Opening video source: {self.source}")
        self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video source: {self.source}")

        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        logger.info(f"Video properties: {width}x{height} @ {self.fps:.2f} FPS")

    def set_detection_callback(self, callback: Callable):
        """
        Set callback function for detection events.

        Args:
            callback: Function(frame_num, detections) to call for each frame
        """
        self.detection_callback = callback

    def process_frame(self, frame) -> List[Dict]:
        """
        Process single frame through YOLO model.

        Args:
            frame: OpenCV frame (numpy array)

        Returns:
            List of detection dictionaries
        """
        # Run inference with tracking if enabled
        if self.enable_tracking:
            results = self.model.track(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                persist=True,
                verbose=False,
            )
        else:
            results = self.model.predict(
                frame,
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False,
            )

        # Extract detections
        detections = []

        if len(results) > 0:
            result = results[0]
            boxes = result.boxes

            for i in range(len(boxes)):
                box = boxes[i]

                # Get bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                # Get class and confidence
                class_id = int(box.cls[0].cpu().numpy())
                confidence = float(box.conf[0].cpu().numpy())

                # Get track ID if tracking is enabled
                track_id = int(box.id[0].cpu().numpy()) if box.id is not None else None

                detection = {
                    "frame_num": self.frame_count,
                    "object_id": track_id if track_id is not None else i,
                    "class_id": class_id,
                    "confidence": confidence,
                    "bbox": {
                        "left": float(x1),
                        "top": float(y1),
                        "width": float(x2 - x1),
                        "height": float(y2 - y1),
                    },
                }
                detections.append(detection)

        return detections

    def run(self):
        """Run video processing loop."""
        if not self.model or not self.cap:
            raise RuntimeError("Processor not initialized. Call initialize() first.")

        logger.info("Starting video processing...")
        self.running = True

        start_time = time.time()
        process_start = time.time()

        try:
            while self.running:
                ret, frame = self.cap.read()

                if not ret:
                    logger.info("End of video reached")
                    break

                self.frame_count += 1

                # Process frame
                detections = self.process_frame(frame)

                # Call detection callback if registered
                if self.detection_callback and detections:
                    self.detection_callback(self.frame_count, detections)

                # Log progress every second
                if self.frame_count % int(self.fps) == 0:
                    elapsed = time.time() - process_start
                    current_fps = self.frame_count / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Frame {self.frame_count}: {len(detections)} detections, "
                        f"Processing FPS: {current_fps:.2f}"
                    )

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error during processing: {e}", exc_info=True)
        finally:
            self.stop()

        total_time = time.time() - start_time
        avg_fps = self.frame_count / total_time if total_time > 0 else 0
        logger.info(
            f"Processing complete: {self.frame_count} frames in {total_time:.2f}s "
            f"(avg {avg_fps:.2f} FPS)"
        )

    def stop(self):
        """Stop processing and cleanup."""
        logger.info("Stopping video processor...")
        self.running = False

        if self.cap:
            self.cap.release()
            self.cap = None

        logger.info("Video processor stopped")
