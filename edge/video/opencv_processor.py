"""
OpenCV-based video processor with YOLO inference and tracking.
Alternative to DeepStream when TensorRT compatibility issues exist.
"""
import logging
import time
from pathlib import Path
from typing import Optional, Callable, Dict, List
import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# COCO class names for visualization
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake',
    'chair', 'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop',
    'mouse', 'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


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
        stream_server=None,
    ):
        """
        Initialize video processor.

        Args:
            source: Video file path or RTSP URL
            model_path: Path to YOLO model (.pt or .onnx)
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
            enable_tracking: Enable object tracking
            stream_server: Optional MJPEGStreamServer for live view
        """
        self.source = source
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.enable_tracking = enable_tracking
        self.stream_server = stream_server

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

    def draw_detections(self, frame, detections: List[Dict]):
        """
        Draw bounding boxes and labels on frame.

        Args:
            frame: OpenCV frame (BGR format)
            detections: List of detection dictionaries

        Returns:
            Annotated frame
        """
        annotated_frame = frame.copy()

        for det in detections:
            bbox = det["bbox"]
            class_id = det["class_id"]
            confidence = det["confidence"]
            object_id = det["object_id"]

            # Get coordinates
            x1 = int(bbox["left"])
            y1 = int(bbox["top"])
            x2 = int(x1 + bbox["width"])
            y2 = int(y1 + bbox["height"])

            # Get class name
            class_name = COCO_CLASSES[class_id] if class_id < len(COCO_CLASSES) else f"Class{class_id}"

            # Color based on class (consistent per class)
            np.random.seed(class_id)
            color = tuple(np.random.randint(50, 255, 3).tolist())

            # Draw bounding box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

            # Prepare label with ID if tracking enabled
            if self.enable_tracking and object_id is not None:
                label = f"ID:{object_id} {class_name} {confidence:.2f}"
            else:
                label = f"{class_name} {confidence:.2f}"

            # Draw label background
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                annotated_frame,
                (x1, y1 - label_height - baseline - 5),
                (x1 + label_width, y1),
                color,
                -1
            )

            # Draw label text
            cv2.putText(
                annotated_frame,
                label,
                (x1, y1 - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        # Add FPS counter
        if self.frame_count > 0:
            fps_text = f"FPS: {self.fps:.1f} | Frame: {self.frame_count}"
            cv2.putText(
                annotated_frame,
                fps_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        return annotated_frame

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

                # Draw detections on frame
                annotated_frame = self.draw_detections(frame, detections)

                # Send to stream server if available
                if self.stream_server:
                    self.stream_server.update_frame(annotated_frame)

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

                    # Update stream server FPS stats if available
                    if self.stream_server:
                        self.stream_server.update_stats(fps=f"{current_fps:.1f}")

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
