"""
AI Detection Module for Dealereye
Uses YOLOv8 for real-time object detection of people and vehicles
Supports both PyTorch (.pt) and TensorRT (.engine) models
"""

from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime
import os
import time

class Detector:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.5, auto_tensorrt=True):
        """
        Initialize the detector with YOLOv8 model

        Args:
            model_path: Path to YOLOv8 model weights (default: yolov8n.pt for nano)
            conf_threshold: Confidence threshold for detections (0-1)
            auto_tensorrt: Automatically use TensorRT engine if available (default: True)
        """
        # Auto-detect TensorRT engine
        if auto_tensorrt and model_path.endswith('.pt'):
            engine_path = model_path.replace('.pt', '.engine')
            if os.path.exists(engine_path):
                print(f"🚀 TensorRT engine found: {engine_path}")
                model_path = engine_path
            else:
                print(f"💡 Using PyTorch model: {model_path}")
                print(f"   To optimize for Jetson, run: python3 optimize_model.py --model {model_path}")

        print(f"Loading YOLOv8 model: {model_path}")
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

        # Detect model type
        self.is_tensorrt = model_path.endswith('.engine')
        self.model_type = "TensorRT" if self.is_tensorrt else "PyTorch"

        # Performance tracking
        self.inference_times = []
        self.total_detections = 0

        # Classes of interest for dealerships
        # COCO dataset: 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck, 63=laptop
        self.target_classes = [0, 2, 3, 5, 7, 63]
        self.class_names = {
            0: "person",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
            63: "laptop"
        }

        print(f"✅ Detector initialized ({self.model_type} backend)")

    def detect(self, frame):
        """
        Run detection on a single frame

        Args:
            frame: OpenCV image (numpy array)

        Returns:
            dict with detections: {
                'detections': [{'class': str, 'confidence': float, 'bbox': [x1,y1,x2,y2]}],
                'count': int,
                'timestamp': str,
                'inference_time_ms': float
            }
        """
        # Track inference time
        start_time = time.time()

        results = self.model(frame, conf=self.conf_threshold, verbose=False)

        inference_time = (time.time() - start_time) * 1000  # Convert to ms
        self.inference_times.append(inference_time)

        # Keep only last 100 times for rolling average
        if len(self.inference_times) > 100:
            self.inference_times.pop(0)

        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])

                # Only keep target classes
                if cls_id in self.target_classes:
                    confidence = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                    detections.append({
                        'class': self.class_names[cls_id],
                        'confidence': round(confidence, 3),
                        'bbox': [round(coord, 2) for coord in bbox]
                    })

        self.total_detections += len(detections)

        return {
            'detections': detections,
            'count': len(detections),
            'timestamp': datetime.now().isoformat(),
            'inference_time_ms': round(inference_time, 2)
        }

    def get_performance_stats(self):
        """
        Get performance statistics

        Returns:
            dict with performance metrics
        """
        if not self.inference_times:
            return {
                'model_type': self.model_type,
                'model_path': self.model_path,
                'avg_inference_ms': 0,
                'fps': 0,
                'total_detections': 0
            }

        avg_time = sum(self.inference_times) / len(self.inference_times)
        fps = 1000 / avg_time if avg_time > 0 else 0

        return {
            'model_type': self.model_type,
            'model_path': self.model_path,
            'avg_inference_ms': round(avg_time, 2),
            'min_inference_ms': round(min(self.inference_times), 2),
            'max_inference_ms': round(max(self.inference_times), 2),
            'fps': round(fps, 1),
            'total_inferences': len(self.inference_times),
            'total_detections': self.total_detections
        }

    def draw_detections(self, frame, detections):
        """
        Draw bounding boxes on frame

        Args:
            frame: OpenCV image
            detections: List of detection dicts from detect()

        Returns:
            Annotated frame
        """
        annotated = frame.copy()

        for det in detections:
            x1, y1, x2, y2 = [int(coord) for coord in det['bbox']]
            label = f"{det['class']} {det['confidence']:.2f}"

            # Different colors for different object types
            if det['class'] == 'person':
                color = (0, 255, 0)  # Green for people
            elif det['class'] == 'laptop':
                color = (0, 165, 255)  # Orange for laptops
            else:
                color = (255, 0, 0)  # Blue for vehicles

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return annotated

    def save_snapshot(self, frame, detections, output_dir="snapshots"):
        """
        Save detection snapshot to disk

        Args:
            frame: OpenCV image
            detections: Detection results
            output_dir: Directory to save snapshots

        Returns:
            Saved file path
        """
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"detection_{timestamp}_{detections['count']}objects.jpg"
        filepath = os.path.join(output_dir, filename)

        # Draw detections on frame
        annotated = self.draw_detections(frame, detections['detections'])
        cv2.imwrite(filepath, annotated)

        return filepath
