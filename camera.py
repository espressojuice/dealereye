"""
Camera Stream Handler for Dealereye
Manages RTSP/IP camera streams and frame processing
"""

import cv2
import threading
import time
from queue import Queue
from datetime import datetime
from collections import deque
import os

class CameraStream:
    def __init__(self, camera_id, stream_url, detector=None):
        """
        Initialize a camera stream

        Args:
            camera_id: Unique identifier for this camera
            stream_url: RTSP URL (e.g., rtsp://192.168.1.100:554/stream)
            detector: Detector instance for running inference
        """
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.detector = detector

        self.cap = None
        self.running = False
        self.thread = None
        self.frame_queue = Queue(maxsize=10)

        self.latest_frame = None
        self.latest_detections = None
        self.last_detection_time = None

        # Clip recording
        self.frame_buffer = deque(maxlen=150)  # ~5 seconds at 30fps
        self.recording_clip = False
        self.clip_writer = None
        self.clip_filename = None

        self.stats = {
            'frames_processed': 0,
            'detections': 0,
            'errors': 0,
            'clips_recorded': 0,
            'status': 'stopped'
        }

    def connect(self):
        """Connect to camera stream"""
        print(f"[{self.camera_id}] Connecting to {self.stream_url}")

        self.cap = cv2.VideoCapture(self.stream_url)

        if not self.cap.isOpened():
            print(f"[{self.camera_id}] Failed to connect")
            self.stats['status'] = 'error'
            return False

        # Set buffer size to reduce latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        print(f"[{self.camera_id}] Connected successfully")
        self.stats['status'] = 'connected'
        return True

    def start(self):
        """Start processing stream in background thread"""
        if self.running:
            print(f"[{self.camera_id}] Already running")
            return

        if not self.connect():
            return

        self.running = True
        self.thread = threading.Thread(target=self._process_stream, daemon=True)
        self.thread.start()
        self.stats['status'] = 'running'

        print(f"[{self.camera_id}] Stream processing started")

    def stop(self):
        """Stop processing stream"""
        print(f"[{self.camera_id}] Stopping stream...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=5)

        if self.cap:
            self.cap.release()

        self.stats['status'] = 'stopped'
        print(f"[{self.camera_id}] Stopped")

    def _process_stream(self):
        """Main loop for processing frames (runs in background thread)"""
        frame_skip = 0
        detection_interval = 5  # Run detection every N frames

        while self.running:
            try:
                ret, frame = self.cap.read()

                if not ret:
                    print(f"[{self.camera_id}] Failed to read frame, reconnecting...")
                    self.stats['errors'] += 1
                    time.sleep(2)

                    # Try to reconnect
                    if not self.connect():
                        time.sleep(5)
                    continue

                self.latest_frame = frame
                self.stats['frames_processed'] += 1

                # Add frame to rolling buffer
                self.frame_buffer.append(frame.copy())

                # Write frame to clip if recording
                if self.recording_clip and self.clip_writer:
                    self.clip_writer.write(frame)
                    self.clip_frames_remaining -= 1

                    # Finish recording if duration reached
                    if self.clip_frames_remaining <= 0:
                        self._finish_clip_recording()

                # Run detection every N frames to reduce CPU load
                if frame_skip % detection_interval == 0 and self.detector:
                    detections = self.detector.detect(frame)

                    if detections['count'] > 0:
                        self.latest_detections = detections
                        self.last_detection_time = datetime.now()
                        self.stats['detections'] += 1

                        print(f"[{self.camera_id}] Detected {detections['count']} objects: "
                              f"{', '.join([d['class'] for d in detections['detections']])}")

                        # Auto-start clip recording on detection
                        if not self.recording_clip:
                            self.start_clip_recording(duration=10)

                frame_skip += 1

                # Small delay to prevent maxing out CPU
                time.sleep(0.01)

            except Exception as e:
                print(f"[{self.camera_id}] Error: {e}")
                self.stats['errors'] += 1
                time.sleep(1)

    def start_clip_recording(self, duration=10, output_dir="clips"):
        """
        Start recording a video clip

        Args:
            duration: Clip duration in seconds
            output_dir: Directory to save clips
        """
        if self.recording_clip:
            print(f"[{self.camera_id}] Already recording a clip")
            return None

        if self.latest_frame is None:
            print(f"[{self.camera_id}] No frames available to record")
            return None

        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.clip_filename = os.path.join(output_dir, f"{self.camera_id}_{timestamp}.mp4")

        # Get frame dimensions
        height, width = self.latest_frame.shape[:2]

        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = 30
        self.clip_writer = cv2.VideoWriter(self.clip_filename, fourcc, fps, (width, height))

        # Write buffered frames (pre-event)
        for frame in self.frame_buffer:
            self.clip_writer.write(frame)

        self.recording_clip = True
        self.clip_frames_remaining = duration * fps

        print(f"[{self.camera_id}] Started recording clip: {self.clip_filename}")
        return self.clip_filename

    def _finish_clip_recording(self):
        """Internal method to finish and close clip recording"""
        if self.clip_writer:
            self.clip_writer.release()
            self.clip_writer = None

        self.recording_clip = False
        self.stats['clips_recorded'] += 1

        filename = self.clip_filename
        self.clip_filename = None

        print(f"[{self.camera_id}] Finished recording clip: {filename}")
        return filename

    def get_latest_frame(self):
        """Get the most recent frame"""
        return self.latest_frame

    def get_latest_detections(self):
        """Get the most recent detection results"""
        return self.latest_detections

    def get_stats(self):
        """Get camera statistics"""
        return {
            'camera_id': self.camera_id,
            'stream_url': self.stream_url,
            **self.stats,
            'last_detection': self.last_detection_time.isoformat() if self.last_detection_time else None
        }


class CameraManager:
    """Manages multiple camera streams"""

    def __init__(self, detector=None):
        self.detector = detector
        self.cameras = {}

    def add_camera(self, camera_id, stream_url):
        """
        Add a new camera stream

        Args:
            camera_id: Unique identifier
            stream_url: RTSP URL

        Returns:
            CameraStream instance
        """
        if camera_id in self.cameras:
            print(f"Camera {camera_id} already exists")
            return self.cameras[camera_id]

        camera = CameraStream(camera_id, stream_url, self.detector)
        self.cameras[camera_id] = camera

        print(f"Added camera: {camera_id}")
        return camera

    def start_camera(self, camera_id):
        """Start a specific camera"""
        if camera_id not in self.cameras:
            print(f"Camera {camera_id} not found")
            return False

        self.cameras[camera_id].start()
        return True

    def stop_camera(self, camera_id):
        """Stop a specific camera"""
        if camera_id not in self.cameras:
            return False

        self.cameras[camera_id].stop()
        return True

    def start_all(self):
        """Start all cameras"""
        for camera_id in self.cameras:
            self.start_camera(camera_id)

    def stop_all(self):
        """Stop all cameras"""
        for camera_id in self.cameras:
            self.stop_camera(camera_id)

    def get_camera(self, camera_id):
        """Get a specific camera"""
        return self.cameras.get(camera_id)

    def get_all_stats(self):
        """Get statistics for all cameras"""
        return {cam_id: cam.get_stats() for cam_id, cam in self.cameras.items()}

    def remove_camera(self, camera_id):
        """Remove a camera"""
        if camera_id in self.cameras:
            self.stop_camera(camera_id)
            del self.cameras[camera_id]
            return True
        return False
