"""
MJPEG streaming server for live video with detections.
Provides HTTP endpoint for browser-based viewing.
"""
import cv2
import logging
from flask import Flask, Response, jsonify
from threading import Thread, Lock
import time

logger = logging.getLogger(__name__)


class MJPEGStreamServer:
    """MJPEG streaming server for live video."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize MJPEG stream server.

        Args:
            host: Host to bind to (0.0.0.0 for all interfaces)
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.current_frame = None
        self.frame_lock = Lock()
        self.server_thread = None
        self.running = False

        # Stats tracking
        self.stats = {
            "camera_ip": "Unknown",
            "resolution": "Unknown",
            "fps": "0.0",
            "model": "YOLOv8n TensorRT FP16"
        }
        self.stats_lock = Lock()

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Simple index page."""
            return """
            <html>
                <head><title>DealerEye Live Stream</title></head>
                <body style="margin:0; background:#000;">
                    <img src="/stream" style="width:100%; height:100vh; object-fit:contain;">
                </body>
            </html>
            """

        @self.app.route('/stream')
        def stream():
            """MJPEG stream endpoint."""
            return Response(
                self._generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @self.app.route('/stats')
        def stats():
            """Camera statistics endpoint."""
            with self.stats_lock:
                return jsonify(self.stats)

    def _generate_frames(self):
        """Generate MJPEG frames."""
        while self.running:
            with self.frame_lock:
                if self.current_frame is not None:
                    # Encode frame as JPEG
                    ret, buffer = cv2.imencode('.jpg', self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            time.sleep(0.033)  # ~30 FPS max

    def update_frame(self, frame):
        """
        Update current frame.

        Args:
            frame: OpenCV frame (BGR format)
        """
        with self.frame_lock:
            self.current_frame = frame.copy()

    def update_stats(self, camera_ip: str = None, resolution: str = None, fps: str = None, model: str = None):
        """
        Update camera statistics.

        Args:
            camera_ip: Camera IP address
            resolution: Video resolution (e.g., "1536x576")
            fps: Frames per second
            model: Model name
        """
        with self.stats_lock:
            if camera_ip is not None:
                self.stats["camera_ip"] = camera_ip
            if resolution is not None:
                self.stats["resolution"] = resolution
            if fps is not None:
                self.stats["fps"] = fps
            if model is not None:
                self.stats["model"] = model

    def start(self):
        """Start streaming server."""
        if self.running:
            logger.warning("Stream server already running")
            return

        self.running = True

        # Start Flask in background thread
        self.server_thread = Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

        logger.info(f"MJPEG stream server started on http://{self.host}:{self.port}/stream")

    def _run_server(self):
        """Run Flask server."""
        # Disable Flask logging
        import logging as flask_logging
        log = flask_logging.getLogger('werkzeug')
        log.setLevel(flask_logging.ERROR)

        self.app.run(host=self.host, port=self.port, threaded=True, debug=False)

    def stop(self):
        """Stop streaming server."""
        self.running = False
        logger.info("MJPEG stream server stopped")
