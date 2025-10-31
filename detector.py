"""
AI Detection Module for Dealereye
Uses YOLOv8 for real-time object detection of people and vehicles
"""

from ultralytics import YOLO
import cv2
import numpy as np
from datetime import datetime
import os

class Detector:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.5):
        """
        Initialize the detector with YOLOv8 model

        Args:
            model_path: Path to YOLOv8 model weights (default: yolov8n.pt for nano)
            conf_threshold: Confidence threshold for detections (0-1)
        """
        print(f"Loading YOLOv8 model: {model_path}")
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold

        # Classes of interest for dealerships
        # COCO dataset: 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck
        self.target_classes = [0, 2, 3, 5, 7]
        self.class_names = {
            0: "person",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }

    def detect(self, frame):
        """
        Run detection on a single frame

        Args:
            frame: OpenCV image (numpy array)

        Returns:
            dict with detections: {
                'detections': [{'class': str, 'confidence': float, 'bbox': [x1,y1,x2,y2]}],
                'count': int,
                'timestamp': str
            }
        """
        results = self.model(frame, conf=self.conf_threshold, verbose=False)

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

        return {
            'detections': detections,
            'count': len(detections),
            'timestamp': datetime.now().isoformat()
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

            # Different colors for people vs vehicles
            color = (0, 255, 0) if det['class'] == 'person' else (255, 0, 0)

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
