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
import json

class CameraStream:
    def __init__(self, camera_id, stream_url, detector=None,
                 detection_interval=None, inference_resolution=None, thresholds=None):
        """
        Initialize a camera stream

        Args:
            camera_id: Unique identifier for this camera
            stream_url: RTSP URL (e.g., rtsp://192.168.1.100:554/stream)
            detector: Detector instance for running inference
            detection_interval: Run detection every N frames (default: 5, higher=faster but less detections)
            inference_resolution: Resize frames for inference (default: None=full res, 640 recommended for speed)
            thresholds: Per-camera detection thresholds dict (e.g., {"person": 50, "laptop": 20})
        """
        self.camera_id = camera_id
        self.stream_url = stream_url
        self.detector = detector

        # Performance tuning (can be set via environment variables or API)
        self.detection_interval = detection_interval or int(os.getenv('DETECTION_INTERVAL', '5'))
        self.inference_resolution = inference_resolution or (int(os.getenv('INFERENCE_WIDTH', '0')) or None)

        # Per-camera AI detection thresholds (percentages)
        # Default to global defaults if not specified
        self.thresholds = thresholds or {
            "person": 50,
            "laptop": 20,
            "car": 25,
            "motorcycle": 25,
            "bus": 25,
            "truck": 25
        }

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

        # FPS tracking
        self.fps_start_time = time.time()
        self.fps_frame_count = 0
        self.current_fps = 0

        # Inference performance tracking
        self.avg_inference_time = 0

        self.stats = {
            'frames_processed': 0,
            'detections': 0,
            'errors': 0,
            'clips_recorded': 0,
            'status': 'stopped',
            'avg_inference_ms': 0
        }

        print(f"[{self.camera_id}] Performance settings: detection_interval={self.detection_interval}, inference_resolution={self.inference_resolution}")
        print(f"[{self.camera_id}] Detection thresholds: {self.thresholds}")

    def connect(self):
        """Connect to camera stream with optimized settings"""
        print(f"[{self.camera_id}] Connecting to {self.stream_url}")

        # Use FFMPEG backend for better RTSP performance
        self.cap = cv2.VideoCapture(self.stream_url, cv2.CAP_FFMPEG)

        if not self.cap.isOpened():
            print(f"[{self.camera_id}] Failed to connect")
            self.stats['status'] = 'error'
            return False

        # Optimize for low latency and performance
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
        self.cap.set(cv2.CAP_PROP_FPS, 30)  # Request 30fps (camera may limit)

        # Get actual stream properties
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"[{self.camera_id}] Connected: {width}x{height} @ {actual_fps}fps")
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

                # Calculate FPS
                self.fps_frame_count += 1
                elapsed = time.time() - self.fps_start_time
                if elapsed >= 1.0:  # Update FPS every second
                    self.current_fps = self.fps_frame_count / elapsed
                    self.fps_frame_count = 0
                    self.fps_start_time = time.time()

                # Add frame to rolling buffer
                self.frame_buffer.append(frame.copy())

                # Write frame to clip if recording
                if self.recording_clip and self.clip_writer:
                    self.clip_writer.write(frame)
                    self.clip_frames_remaining -= 1

                    # Finish recording if duration reached
                    if self.clip_frames_remaining <= 0:
                        self._finish_clip_recording()

                # Run detection every N frames to reduce GPU load
                if frame_skip % self.detection_interval == 0 and self.detector:
                    # Resize frame for inference if configured (big performance gain)
                    inference_frame = frame
                    if self.inference_resolution:
                        h, w = frame.shape[:2]
                        scale = self.inference_resolution / max(h, w)
                        if scale < 1.0:  # Only downscale, never upscale
                            new_w = int(w * scale)
                            new_h = int(h * scale)
                            inference_frame = cv2.resize(frame, (new_w, new_h))

                    # Run detection with per-camera thresholds
                    start_inference = time.time()
                    detections = self.detector.detect(inference_frame, custom_thresholds=self.thresholds)
                    inference_time = (time.time() - start_inference) * 1000  # ms

                    # Track inference performance
                    self.avg_inference_time = (self.avg_inference_time * 0.9) + (inference_time * 0.1)
                    self.stats['avg_inference_ms'] = round(self.avg_inference_time, 1)

                    if detections['count'] > 0:
                        self.latest_detections = detections
                        self.last_detection_time = datetime.now()
                        self.stats['detections'] += 1

                        print(f"[{self.camera_id}] Detected {detections['count']} objects: "
                              f"{', '.join([d['class'] for d in detections['detections']])} "
                              f"({inference_time:.1f}ms)")

                        # Auto-start clip recording on detection
                        if not self.recording_clip:
                            self.start_clip_recording(duration=10)

                frame_skip += 1

                # Small delay to prevent maxing out GPU
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
        # Get detector performance if available
        avg_inference_ms = 0
        if self.detector and hasattr(self.detector, 'get_performance_stats'):
            perf = self.detector.get_performance_stats()
            avg_inference_ms = perf.get('avg_inference_ms', 0)

        return {
            'camera_id': self.camera_id,
            'stream_url': self.stream_url,
            'running': self.running,  # Boolean for UI
            'status': self.stats['status'],  # String status
            'fps': self.current_fps,
            'frames_processed': self.stats['frames_processed'],
            'total_detections': self.stats['detections'],
            'errors': self.stats['errors'],
            'clips_recorded': self.stats['clips_recorded'],
            'avg_inference_ms': avg_inference_ms,
            'last_detection': self.last_detection_time.isoformat() if self.last_detection_time else None
        }


class CameraManager:
    """Manages multiple camera streams"""

    def __init__(self, detector=None, config_file="/app/config/cameras.json"):
        self.detector = detector
        self.cameras = {}
        self.config_file = config_file

        # Load saved camera configurations
        self.load_config()

    def add_camera(self, camera_id, stream_url, auto_start=False):
        """
        Add a new camera stream

        Args:
            camera_id: Unique identifier
            stream_url: RTSP URL
            auto_start: Whether to start the camera immediately

        Returns:
            CameraStream instance

        Raises:
            ValueError: If camera_id or stream_url is invalid
            Exception: If camera creation fails
        """
        # Validate inputs
        if not camera_id or not isinstance(camera_id, str):
            raise ValueError("camera_id must be a non-empty string")

        if not stream_url or not isinstance(stream_url, str):
            raise ValueError("stream_url must be a non-empty string")

        if camera_id in self.cameras:
            print(f"[CameraManager] Camera {camera_id} already exists, returning existing camera")
            return self.cameras[camera_id]

        print(f"[CameraManager] Adding camera: {camera_id} with URL: {stream_url}")

        try:
            camera = CameraStream(camera_id, stream_url, self.detector)
            self.cameras[camera_id] = camera

            print(f"[CameraManager] Camera {camera_id} created successfully")

            # Save configuration
            self.save_config()

            if auto_start:
                print(f"[CameraManager] Auto-starting camera {camera_id}")
                camera.start()

            return camera

        except Exception as e:
            # Clean up if something went wrong
            if camera_id in self.cameras:
                del self.cameras[camera_id]
            error_msg = f"Failed to create camera {camera_id}: {str(e)}"
            print(f"[CameraManager] ERROR: {error_msg}")
            raise Exception(error_msg)

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

    def remove_camera(self, camera_id, force=False):
        """
        Remove a camera

        Args:
            camera_id: Camera ID to remove
            force: If True, remove from config even if not in memory

        Returns:
            tuple: (success: bool, message: str)
        """
        print(f"[CameraManager] Attempting to remove camera: {camera_id}")
        print(f"[CameraManager] Currently loaded cameras: {list(self.cameras.keys())}")

        # Check if camera exists in memory
        if camera_id in self.cameras:
            print(f"[CameraManager] Camera {camera_id} found in memory, removing...")
            self.stop_camera(camera_id)
            del self.cameras[camera_id]
            self.save_config()
            print(f"[CameraManager] Camera {camera_id} removed successfully")
            return True, f"Camera {camera_id} removed successfully"

        # Camera not in memory - check if it's in the config file
        print(f"[CameraManager] Camera {camera_id} not found in memory")

        if force:
            print(f"[CameraManager] Force mode enabled, attempting to remove from config file...")
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        config = json.load(f)

                    cameras = config.get("cameras", [])
                    original_count = len(cameras)
                    cameras = [c for c in cameras if c.get("camera_id") != camera_id]

                    if len(cameras) < original_count:
                        config["cameras"] = cameras
                        with open(self.config_file, 'w') as f:
                            json.dump(config, f, indent=2)
                        print(f"[CameraManager] Removed {camera_id} from config file")
                        return True, f"Camera {camera_id} force-removed from config"
                    else:
                        print(f"[CameraManager] Camera {camera_id} not found in config file either")
                        return False, f"Camera {camera_id} not found in memory or config file"
                else:
                    print(f"[CameraManager] Config file does not exist")
                    return False, "Config file not found"
            except Exception as e:
                error_msg = f"Error force-removing camera: {e}"
                print(f"[CameraManager] {error_msg}")
                return False, error_msg

        return False, f"Camera {camera_id} not found (loaded cameras: {list(self.cameras.keys())})"

    def save_config(self):
        """Save camera configurations to JSON file"""
        try:
            config_dir = os.path.dirname(self.config_file)
            if config_dir:
                os.makedirs(config_dir, exist_ok=True)

            config = {
                "cameras": [
                    {
                        "camera_id": cam_id,
                        "stream_url": cam.stream_url,
                        "thresholds": cam.thresholds,
                        "detection_interval": cam.detection_interval,
                        "inference_resolution": cam.inference_resolution
                    }
                    for cam_id, cam in self.cameras.items()
                ]
            }

            # Write to temp file first, then rename (atomic operation)
            temp_file = self.config_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(config, f, indent=2)

            # Rename temp file to actual config file
            os.replace(temp_file, self.config_file)

            print(f"[CameraManager] Saved {len(config['cameras'])} camera(s) to {self.config_file}")

        except Exception as e:
            print(f"[CameraManager] ERROR saving config: {e}")
            raise

    def load_config(self):
        """Load camera configurations from JSON file and auto-start them"""
        try:
            if not os.path.exists(self.config_file):
                print(f"[CameraManager] No config file found at {self.config_file}, starting fresh")
                return

            print(f"[CameraManager] Loading configuration from {self.config_file}")

            with open(self.config_file, 'r') as f:
                config = json.load(f)

            cameras = config.get("cameras", [])

            if not cameras:
                print("[CameraManager] No cameras in config")
                return

            print(f"[CameraManager] Found {len(cameras)} camera(s) in config, loading...")

            loaded_count = 0
            failed_count = 0

            for cam_config in cameras:
                camera_id = cam_config.get("camera_id")
                stream_url = cam_config.get("stream_url")
                thresholds = cam_config.get("thresholds")
                detection_interval = cam_config.get("detection_interval")
                inference_resolution = cam_config.get("inference_resolution")

                # Validate config entry
                if not camera_id or not stream_url:
                    print(f"[CameraManager] WARNING: Skipping invalid config entry: {cam_config}")
                    failed_count += 1
                    continue

                try:
                    # Add camera (don't auto-start yet) with saved settings
                    camera = CameraStream(
                        camera_id,
                        stream_url,
                        self.detector,
                        detection_interval=detection_interval,
                        inference_resolution=inference_resolution,
                        thresholds=thresholds
                    )
                    self.cameras[camera_id] = camera
                    print(f"[CameraManager] Loaded camera: {camera_id}")

                    # Auto-start the camera
                    camera.start()
                    loaded_count += 1

                except Exception as e:
                    print(f"[CameraManager] ERROR: Failed to load camera {camera_id}: {e}")
                    failed_count += 1
                    # Clean up if it was partially added
                    if camera_id in self.cameras:
                        del self.cameras[camera_id]

            print(f"[CameraManager] Successfully loaded {loaded_count} camera(s), {failed_count} failed")

            # If we had failures, save config to clean it up
            if failed_count > 0:
                print(f"[CameraManager] Cleaning up config file to remove failed entries")
                self.save_config()

        except json.JSONDecodeError as e:
            print(f"[CameraManager] ERROR: Invalid JSON in config file: {e}")
            print(f"[CameraManager] Starting with empty camera list")
        except Exception as e:
            print(f"[CameraManager] ERROR loading config: {e}")
            print(f"[CameraManager] Starting with empty camera list")
