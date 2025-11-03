from flask import Flask, request, jsonify, send_file, Response, render_template_string
import boto3
import os
import io
import cv2
import subprocess
import requests
import json
from detector import Detector
from camera import CameraManager

app = Flask(__name__)

BUCKET = "dealereye"
ENDPOINT = "https://s3.us-east-1.wasabisys.com"

s3 = boto3.client("s3", endpoint_url=ENDPOINT)

# Initialize AI detector and camera manager
print("Initializing Dealereye AI system...")
# Per-class confidence thresholds: person=50%, laptop=20%, vehicles=25%
class_thresholds = {
    0: 0.50,   # person
    63: 0.20,  # laptop
    2: 0.25,   # car
    3: 0.25,   # motorcycle
    5: 0.25,   # bus
    7: 0.25    # truck
}
detector = Detector(model_path="yolov8n.pt", conf_threshold=0.25, class_thresholds=class_thresholds)
camera_manager = CameraManager(detector=detector)
print("System ready!")

@app.route("/")
def home():
    stats = camera_manager.get_all_stats()
    perf_stats = detector.get_performance_stats()
    return jsonify({
        "status": "✅ Dealereye AI system running",
        "bucket": BUCKET,
        "cameras": len(stats),
        "camera_stats": stats,
        "ai_performance": perf_stats
    })

@app.route("/dashboard")
def dashboard():
    """Web dashboard for viewing live camera feeds"""
    stats = camera_manager.get_all_stats()
    camera_list = list(stats.keys())

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dealereye Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #1a1a1a;
                color: #fff;
                margin: 0;
                padding: 20px;
            }
            h1 {
                text-align: center;
                color: #4CAF50;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .add-camera-section {
                background: #2a2a2a;
                border-radius: 8px;
                padding: 20px;
                margin-top: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            .add-camera-section h2 {
                margin-top: 0;
                color: #4CAF50;
            }
            .form-group {
                margin-bottom: 15px;
            }
            .form-group label {
                display: block;
                margin-bottom: 5px;
                color: #888;
                font-size: 14px;
            }
            .form-group input {
                width: 100%;
                padding: 10px;
                background: #1a1a1a;
                border: 1px solid #444;
                border-radius: 4px;
                color: #fff;
                font-size: 14px;
                box-sizing: border-box;
            }
            .form-group input:focus {
                outline: none;
                border-color: #4CAF50;
            }
            .btn {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
                margin-right: 10px;
            }
            .btn:hover {
                background: #45a049;
            }
            .btn-danger {
                background: #f44336;
            }
            .btn-danger:hover {
                background: #da190b;
            }
            .btn-warning {
                background: #ff9800;
            }
            .btn-warning:hover {
                background: #e68900;
            }
            .btn-small {
                padding: 6px 12px;
                font-size: 14px;
            }
            .camera-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            .camera-card {
                background: #2a2a2a;
                border-radius: 8px;
                padding: 15px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            .camera-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }
            .camera-header h2 {
                margin: 0;
                color: #4CAF50;
            }
            .camera-controls {
                display: flex;
                gap: 8px;
            }
            .stream-container {
                position: relative;
                width: 100%;
                background: #000;
                border-radius: 4px;
                overflow: hidden;
            }
            .stream-container img {
                width: 100%;
                height: auto;
                display: block;
            }
            .stream-url {
                font-size: 12px;
                color: #666;
                margin-bottom: 10px;
                word-break: break-all;
            }
            .stats {
                margin-top: 15px;
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
            }
            .stat-item {
                background: #1a1a1a;
                padding: 10px;
                border-radius: 4px;
            }
            .stat-label {
                color: #888;
                font-size: 12px;
                text-transform: uppercase;
            }
            .stat-value {
                font-size: 18px;
                font-weight: bold;
                color: #4CAF50;
            }
            .no-cameras {
                text-align: center;
                padding: 60px 20px;
                background: #2a2a2a;
                border-radius: 8px;
                margin-top: 30px;
            }
            .no-cameras h2 {
                color: #888;
            }
            .message {
                padding: 10px;
                border-radius: 4px;
                margin-bottom: 15px;
            }
            .message-success {
                background: #4CAF50;
                color: white;
            }
            .message-error {
                background: #f44336;
                color: white;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Dealereye AI Dashboard</h1>

            <!-- Update Section -->
            <div class="add-camera-section" id="update-section">
                <h2>🔄 System Updates</h2>
                <div id="update-message"></div>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button class="btn" onclick="checkForUpdates()">Check for Updates</button>
                    <button class="btn btn-warning" id="update-btn" onclick="applyUpdate()" style="display: none;">Update Now</button>
                    <span id="version-info" style="color: #888; font-size: 14px;"></span>
                </div>
            </div>

            <!-- AI Detection Settings -->
            <div class="add-camera-section">
                <h2>🎯 AI Detection Thresholds</h2>
                <div id="threshold-message"></div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px;">
                    <div class="form-group">
                        <label for="thresh_person">👤 Person: <span id="val_person">50</span>%</label>
                        <input type="range" id="thresh_person" min="10" max="90" value="50" step="5"
                               oninput="document.getElementById('val_person').textContent = this.value"
                               style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <label for="thresh_laptop">💻 Laptop: <span id="val_laptop">20</span>%</label>
                        <input type="range" id="thresh_laptop" min="10" max="90" value="20" step="5"
                               oninput="document.getElementById('val_laptop').textContent = this.value"
                               style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <label for="thresh_car">🚗 Car: <span id="val_car">25</span>%</label>
                        <input type="range" id="thresh_car" min="10" max="90" value="25" step="5"
                               oninput="document.getElementById('val_car').textContent = this.value"
                               style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <label for="thresh_motorcycle">🏍️ Motorcycle: <span id="val_motorcycle">25</span>%</label>
                        <input type="range" id="thresh_motorcycle" min="10" max="90" value="25" step="5"
                               oninput="document.getElementById('val_motorcycle').textContent = this.value"
                               style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <label for="thresh_bus">🚌 Bus: <span id="val_bus">25</span>%</label>
                        <input type="range" id="thresh_bus" min="10" max="90" value="25" step="5"
                               oninput="document.getElementById('val_bus').textContent = this.value"
                               style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <label for="thresh_truck">🚚 Truck: <span id="val_truck">25</span>%</label>
                        <input type="range" id="thresh_truck" min="10" max="90" value="25" step="5"
                               oninput="document.getElementById('val_truck').textContent = this.value"
                               style="width: 100%;">
                    </div>
                </div>
                <button type="button" class="btn" onclick="updateThresholds()">Apply Thresholds</button>
            </div>

            <!-- Add Camera Section -->
            <div class="add-camera-section">
                <h2>➕ Add Camera</h2>
                <div id="add-message"></div>
                <form id="add-camera-form">
                    <div class="form-group">
                        <label for="camera_id">Camera ID</label>
                        <input type="text" id="camera_id" name="camera_id" placeholder="e.g., front_gate" required>
                    </div>
                    <div class="form-group">
                        <label for="stream_url">RTSP Stream URL</label>
                        <input type="text" id="stream_url" name="stream_url" placeholder="rtsp://username:password@ip:port/path" required>
                    </div>
                    <button type="submit" class="btn">Add Camera</button>
                </form>
            </div>

            <!-- Camera Grid -->
            {% if camera_list %}
            <div class="camera-grid" id="camera-grid">
                {% for camera_id in camera_list %}
                <div class="camera-card" id="card-{{ camera_id }}">
                    <div class="camera-header">
                        <h2>{{ camera_id }}</h2>
                        <div class="camera-controls">
                            <button class="btn btn-small btn-warning" onclick="toggleCamera('{{ camera_id }}')">
                                <span id="toggle-{{ camera_id }}">Stop</span>
                            </button>
                            <button class="btn btn-small btn-danger" onclick="removeCamera('{{ camera_id }}')">Remove</button>
                        </div>
                    </div>
                    <div class="stream-url" id="url-{{ camera_id }}">Loading URL...</div>
                    <div class="stream-container">
                        <img src="/cameras/{{ camera_id }}/stream" alt="{{ camera_id }} stream">
                    </div>
                    <div class="stats" id="stats-{{ camera_id }}">
                        <div class="stat-item">
                            <div class="stat-label">Status</div>
                            <div class="stat-value" id="status-{{ camera_id }}">Loading...</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">FPS</div>
                            <div class="stat-value" id="fps-{{ camera_id }}">--</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Detections</div>
                            <div class="stat-value" id="detections-{{ camera_id }}">--</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">AI Inference</div>
                            <div class="stat-value" id="inference-{{ camera_id }}">--</div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="no-cameras" id="no-cameras-msg">
                <h2>No cameras configured</h2>
                <p>Add a camera using the form above to get started.</p>
            </div>
            {% endif %}
        </div>

        <script>
            // Add camera
            document.getElementById('add-camera-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                const cameraId = document.getElementById('camera_id').value;
                const streamUrl = document.getElementById('stream_url').value;
                const messageDiv = document.getElementById('add-message');

                try {
                    const response = await fetch('/cameras', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({camera_id: cameraId, stream_url: streamUrl})
                    });

                    const data = await response.json();

                    if (response.ok) {
                        messageDiv.innerHTML = '<div class="message message-success">Camera added successfully!</div>';
                        document.getElementById('add-camera-form').reset();

                        // Start the camera
                        await fetch(`/cameras/${cameraId}/start`, {method: 'POST'});

                        // Reload page after 1 second
                        setTimeout(() => location.reload(), 1000);
                    } else {
                        messageDiv.innerHTML = `<div class="message message-error">Error: ${data.error}</div>`;
                    }
                } catch (err) {
                    messageDiv.innerHTML = `<div class="message message-error">Error: ${err.message}</div>`;
                }
            });

            // Remove camera
            async function removeCamera(cameraId, force = false) {
                if (!force && !confirm(`Are you sure you want to remove camera "${cameraId}"?`)) {
                    return;
                }

                try {
                    // Use POST endpoint with camera_id in body to avoid URL encoding issues
                    const response = await fetch('/cameras/remove', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            camera_id: cameraId,
                            force: force
                        })
                    });

                    if (response.ok) {
                        const result = await response.json();
                        alert(result.message || 'Camera removed successfully');
                        location.reload();
                    } else {
                        const error = await response.json().catch(() => ({error: 'Failed to parse error response'}));
                        console.error('Remove camera error:', error);

                        // If force is available, offer it as an option
                        if (error.force_available && !force) {
                            if (confirm(`Failed to remove camera: ${error.error}\n\nWould you like to force-remove it? (This will remove it from config even if it is not loaded in memory)`)) {
                                await removeCamera(cameraId, true);
                            }
                        } else {
                            alert(`Failed to remove camera: ${error.error || 'Unknown error'}`);
                        }
                    }
                } catch (err) {
                    console.error('Remove camera exception:', err);
                    alert('Error: ' + err.message);
                }
            }

            // Toggle camera start/stop
            async function toggleCamera(cameraId) {
                try {
                    // Get current state from server first
                    const statsResponse = await fetch(`/cameras/${cameraId}/stats`);
                    const stats = await statsResponse.json();
                    const isRunning = stats.running;
                    const action = isRunning ? 'stop' : 'start';

                    // Send the toggle request
                    const response = await fetch(`/cameras/${cameraId}/${action}`, {method: 'POST'});
                    if (response.ok) {
                        // Update UI immediately for responsiveness
                        document.getElementById(`toggle-${cameraId}`).textContent = isRunning ? 'Start' : 'Stop';
                        document.getElementById(`status-${cameraId}`).textContent = isRunning ? '⚠️ Stopped' : '✅ Running';
                        // Then refresh all stats after a short delay
                        setTimeout(updateStats, 1000);
                    } else {
                        alert('Failed to toggle camera');
                    }
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            }

            // Update stats every 2 seconds
            async function updateStats() {
                const cameras = {{ camera_list | tojson }};
                console.log('updateStats called for cameras:', cameras);

                for (const cameraId of cameras) {
                    try {
                        const response = await fetch(`/cameras/${cameraId}/stats`);

                        if (!response.ok) {
                            console.error(`Failed to fetch stats for ${cameraId}: ${response.status}`);
                            continue;
                        }

                        const data = await response.json();
                        console.log(`Stats for ${cameraId}:`, data);

                        // Update all stats with proper fallbacks
                        const statusEl = document.getElementById(`status-${cameraId}`);
                        const fpsEl = document.getElementById(`fps-${cameraId}`);
                        const detectionsEl = document.getElementById(`detections-${cameraId}`);
                        const inferenceEl = document.getElementById(`inference-${cameraId}`);
                        const urlEl = document.getElementById(`url-${cameraId}`);
                        const toggleEl = document.getElementById(`toggle-${cameraId}`);

                        if (statusEl) statusEl.textContent = data.running ? '✅ Running' : '⚠️ Stopped';
                        if (fpsEl) fpsEl.textContent = data.fps ? data.fps.toFixed(1) : '0.0';
                        if (detectionsEl) detectionsEl.textContent = data.total_detections || 0;
                        if (inferenceEl) inferenceEl.textContent = data.avg_inference_ms ? `${data.avg_inference_ms.toFixed(1)}ms` : '0ms';
                        if (urlEl) urlEl.textContent = `RTSP: ${data.stream_url || 'Unknown'}`;
                        if (toggleEl) toggleEl.textContent = data.running ? 'Stop' : 'Start';

                        console.log(`Updated UI for ${cameraId}`);
                    } catch (err) {
                        console.error(`Error fetching stats for ${cameraId}:`, err);
                        // Set error state in UI
                        const statusEl = document.getElementById(`status-${cameraId}`);
                        if (statusEl) statusEl.textContent = '❌ Error';
                    }
                }
            }

            // Initial update and set interval
            if ({{ camera_list | tojson }}.length > 0) {
                // Call updateStats immediately and set up interval
                setTimeout(() => {
                    updateStats();
                    setInterval(updateStats, 2000);
                }, 100);
            }

            // Update system functions
            async function checkForUpdates() {
                console.log('checkForUpdates called');
                const messageDiv = document.getElementById('update-message');
                const versionInfo = document.getElementById('version-info');
                const updateBtn = document.getElementById('update-btn');

                if (!messageDiv) {
                    console.error('update-message element not found');
                    return;
                }

                messageDiv.innerHTML = '<div class="message" style="background: #666;">⏳ Checking for updates...</div>';

                try {
                    console.log('Fetching /update/check');
                    const response = await fetch('/update/check');
                    console.log('Response status:', response.status);

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }

                    const data = await response.json();
                    console.log('Update check data:', data);

                    if (data.update_available) {
                        messageDiv.innerHTML = '<div class="message message-success">✨ Update available! Click "Update Now" to install.</div>';
                        versionInfo.textContent = `Current: ${data.local_version} → Latest: ${data.latest_version}`;
                        updateBtn.style.display = 'inline-block';
                    } else {
                        messageDiv.innerHTML = '<div class="message" style="background: #4CAF50;">✅ You are running the latest version!</div>';
                        versionInfo.textContent = `Version: ${data.local_version}`;
                        updateBtn.style.display = 'none';
                        // Keep the "up to date" message visible
                        setTimeout(() => {
                            messageDiv.innerHTML = '';
                        }, 3000);
                    }
                } catch (err) {
                    console.error('Update check error:', err);
                    messageDiv.innerHTML = '<div class="message message-error">❌ Error: ' + err.message + '</div>';
                }
            }

            async function applyUpdate() {
                if (!confirm('This will update the system and restart the container. Continue?')) {
                    return;
                }

                const messageDiv = document.getElementById('update-message');
                const updateBtn = document.getElementById('update-btn');

                messageDiv.innerHTML = '<div class="message" style="background: #ff9800;">⏳ Updating system...</div>';
                updateBtn.disabled = true;

                try {
                    const response = await fetch('/update/apply', {method: 'POST'});
                    const data = await response.json();

                    if (data.status === 'manual') {
                        messageDiv.innerHTML = `<div class="message" style="background: #2196F3;">
                            📋 Please run this command on your Jetson:<br>
                            <code style="background: #000; padding: 5px; display: block; margin-top: 10px; word-break: break-all;">
                                ${data.command}
                            </code>
                        </div>`;
                    } else {
                        messageDiv.innerHTML = '<div class="message message-success">✅ Update complete! Refreshing in 5 seconds...</div>';
                        setTimeout(() => location.reload(), 5000);
                    }
                } catch (err) {
                    messageDiv.innerHTML = '<div class="message message-error">Error applying update</div>';
                    updateBtn.disabled = false;
                }
            }

            // Load and update detection thresholds
            async function loadThresholds() {
                try {
                    const response = await fetch('/thresholds');
                    const thresholds = await response.json();

                    // Update sliders with current values
                    if (thresholds.person) {
                        document.getElementById('thresh_person').value = thresholds.person;
                        document.getElementById('val_person').textContent = thresholds.person;
                    }
                    if (thresholds.laptop) {
                        document.getElementById('thresh_laptop').value = thresholds.laptop;
                        document.getElementById('val_laptop').textContent = thresholds.laptop;
                    }
                    if (thresholds.car) {
                        document.getElementById('thresh_car').value = thresholds.car;
                        document.getElementById('val_car').textContent = thresholds.car;
                    }
                    if (thresholds.motorcycle) {
                        document.getElementById('thresh_motorcycle').value = thresholds.motorcycle;
                        document.getElementById('val_motorcycle').textContent = thresholds.motorcycle;
                    }
                    if (thresholds.bus) {
                        document.getElementById('thresh_bus').value = thresholds.bus;
                        document.getElementById('val_bus').textContent = thresholds.bus;
                    }
                    if (thresholds.truck) {
                        document.getElementById('thresh_truck').value = thresholds.truck;
                        document.getElementById('val_truck').textContent = thresholds.truck;
                    }
                } catch (err) {
                    console.error('Error loading thresholds:', err);
                }
            }

            async function updateThresholds() {
                const messageDiv = document.getElementById('threshold-message');

                try {
                    const thresholds = {
                        person: parseInt(document.getElementById('thresh_person').value),
                        laptop: parseInt(document.getElementById('thresh_laptop').value),
                        car: parseInt(document.getElementById('thresh_car').value),
                        motorcycle: parseInt(document.getElementById('thresh_motorcycle').value),
                        bus: parseInt(document.getElementById('thresh_bus').value),
                        truck: parseInt(document.getElementById('thresh_truck').value)
                    };

                    const response = await fetch('/thresholds', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(thresholds)
                    });

                    const data = await response.json();

                    if (response.ok) {
                        messageDiv.innerHTML = '<div class="message message-success">✅ Thresholds updated! Changes are active now.</div>';
                        setTimeout(() => {
                            messageDiv.innerHTML = '';
                        }, 3000);
                    } else {
                        messageDiv.innerHTML = `<div class="message message-error">❌ Error: ${data.error}</div>`;
                    }
                } catch (err) {
                    messageDiv.innerHTML = `<div class="message message-error">❌ Error: ${err.message}</div>`;
                }
            }

            // Initialize on page load
            window.addEventListener('DOMContentLoaded', function() {
                console.log('Dashboard loaded');

                // Load current thresholds
                loadThresholds();

                // Check for updates on page load
                if (typeof checkForUpdates === 'function') {
                    checkForUpdates();
                } else {
                    console.error('checkForUpdates function not defined');
                }
            });
        </script>
    </body>
    </html>
    """

    return render_template_string(html, camera_list=camera_list)

@app.route("/performance", methods=["GET"])
def performance():
    """Get AI model performance statistics"""
    return jsonify(detector.get_performance_stats())

# === Camera Management Endpoints ===

@app.route("/cameras", methods=["GET"])
def list_cameras():
    """List all cameras and their status"""
    return jsonify(camera_manager.get_all_stats())

@app.route("/cameras", methods=["POST"])
def add_camera():
    """Add a new camera. Body: {camera_id: str, stream_url: str}"""
    data = request.get_json()

    # Validate input
    if not data or "camera_id" not in data or "stream_url" not in data:
        return jsonify({"error": "camera_id and stream_url required"}), 400

    camera_id = data["camera_id"].strip()
    stream_url = data["stream_url"].strip()

    # Validate camera_id
    if not camera_id:
        return jsonify({"error": "camera_id cannot be empty"}), 400

    # Prevent camera_id from being a URL (common mistake - swapping camera_id and stream_url)
    if camera_id.startswith("rtsp://") or camera_id.startswith("http://") or camera_id.startswith("https://") or "://" in camera_id:
        return jsonify({
            "error": "camera_id cannot be a URL. Did you swap camera_id and stream_url?",
            "hint": "camera_id should be a simple identifier like 'Backyard' or 'Front Door'"
        }), 400

    # Validate stream_url
    if not stream_url:
        return jsonify({"error": "stream_url cannot be empty"}), 400

    if not (stream_url.startswith("rtsp://") or stream_url.startswith("http://") or stream_url.startswith("https://")):
        return jsonify({"error": "stream_url must start with rtsp://, http://, or https://"}), 400

    # Check if camera already exists
    if camera_manager.get_camera(camera_id):
        return jsonify({"error": f"Camera {camera_id} already exists"}), 409

    # Add camera with error handling
    try:
        camera = camera_manager.add_camera(camera_id, stream_url)
        return jsonify({
            "message": f"Camera {camera_id} added successfully",
            "camera": camera.get_stats()
        })
    except Exception as e:
        print(f"[API] Error adding camera {camera_id}: {e}")
        return jsonify({"error": f"Failed to add camera: {str(e)}"}), 500

@app.route("/cameras/<camera_id>/start", methods=["POST"])
def start_camera(camera_id):
    """Start a specific camera"""
    if camera_manager.start_camera(camera_id):
        return jsonify({"message": f"Camera {camera_id} started"})
    return jsonify({"error": f"Camera {camera_id} not found"}), 404

@app.route("/cameras/<camera_id>/stop", methods=["POST"])
def stop_camera(camera_id):
    """Stop a specific camera"""
    if camera_manager.stop_camera(camera_id):
        return jsonify({"message": f"Camera {camera_id} stopped"})
    return jsonify({"error": f"Camera {camera_id} not found"}), 404

@app.route("/cameras/<camera_id>", methods=["DELETE"])
def remove_camera(camera_id):
    """Remove a camera (URL path method)"""
    # Check if force parameter is set
    force = request.args.get('force', 'false').lower() == 'true'

    success, message = camera_manager.remove_camera(camera_id, force=force)

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({
            "error": message,
            "camera_id": camera_id,
            "force_available": not force  # Suggest force option if not already used
        }), 404

@app.route("/cameras/remove", methods=["POST"])
def remove_camera_post():
    """Remove a camera (POST body method - handles special characters better)"""
    data = request.get_json()

    if not data or "camera_id" not in data:
        return jsonify({"error": "camera_id required in request body"}), 400

    camera_id = data["camera_id"]
    force = data.get("force", False)

    print(f"[API] Remove camera request: camera_id={camera_id}, force={force}")

    success, message = camera_manager.remove_camera(camera_id, force=force)

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({
            "error": message,
            "camera_id": camera_id,
            "force_available": not force  # Suggest force option if not already used
        }), 404

@app.route("/cameras/<camera_id>/stats", methods=["GET"])
def camera_stats(camera_id):
    """Get statistics for a specific camera"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404
    return jsonify(camera.get_stats())

@app.route("/cameras/<camera_id>/detections", methods=["GET"])
def camera_detections(camera_id):
    """Get latest detections from a camera"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404

    detections = camera.get_latest_detections()
    if not detections:
        return jsonify({"message": "No detections yet", "detections": None})

    return jsonify(detections)

@app.route("/cameras/<camera_id>/snapshot", methods=["GET"])
def camera_snapshot(camera_id):
    """Get current frame from camera as JPEG"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404

    frame = camera.get_latest_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 404

    # Draw detections if available
    detections = camera.get_latest_detections()
    if detections and detections['detections']:
        frame = detector.draw_detections(frame, detections['detections'])

    # Encode as JPEG
    _, buffer = cv2.imencode('.jpg', frame)
    return Response(buffer.tobytes(), mimetype='image/jpeg')

@app.route("/cameras/<camera_id>/stream", methods=["GET"])
def camera_stream(camera_id):
    """Get live MJPEG stream with AI detections"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404

    def generate():
        """Generate MJPEG stream"""
        import time
        while True:
            frame = camera.get_latest_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # Draw detections
            detections = camera.get_latest_detections()
            if detections and detections['detections']:
                frame = detector.draw_detections(frame, detections['detections'])

            # Encode frame
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()

            # Yield as MJPEG
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            time.sleep(0.033)  # ~30 FPS

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/cameras/<camera_id>/snapshot/save", methods=["POST"])
def save_snapshot(camera_id):
    """Save snapshot with detections and upload to Wasabi"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404

    frame = camera.get_latest_frame()
    detections = camera.get_latest_detections()

    if frame is None:
        return jsonify({"error": "No frame available"}), 404

    if not detections or detections['count'] == 0:
        return jsonify({"message": "No detections to save"}), 200

    # Save locally
    filepath = detector.save_snapshot(frame, detections)

    # Upload to Wasabi
    with open(filepath, 'rb') as f:
        s3_key = f"snapshots/{camera_id}/{os.path.basename(filepath)}"
        s3.upload_fileobj(f, BUCKET, s3_key)

    return jsonify({
        "message": "Snapshot saved and uploaded",
        "local_path": filepath,
        "s3_key": s3_key,
        "detections": detections
    })

@app.route("/cameras/<camera_id>/record", methods=["POST"])
def record_clip(camera_id):
    """Start recording a video clip. Body: {duration: int (seconds)}"""
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        return jsonify({"error": f"Camera {camera_id} not found"}), 404

    data = request.get_json() or {}
    duration = data.get("duration", 10)

    filepath = camera.start_clip_recording(duration=duration)

    if not filepath:
        return jsonify({"error": "Failed to start recording"}), 500

    return jsonify({
        "message": f"Recording {duration}s clip",
        "filepath": filepath
    })

@app.route("/clips/upload/<path:filename>", methods=["POST"])
def upload_clip(filename):
    """Upload a recorded clip to Wasabi"""
    if not os.path.exists(filename):
        return jsonify({"error": "File not found"}), 404

    with open(filename, 'rb') as f:
        s3_key = f"clips/{os.path.basename(filename)}"
        s3.upload_fileobj(f, BUCKET, s3_key)

    return jsonify({
        "message": "Clip uploaded",
        "s3_key": s3_key,
        "local_path": filename
    })

# === Wasabi Storage Endpoints ===

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    s3.upload_fileobj(file, BUCKET, file.filename)
    return jsonify({"message": f"Uploaded {file.filename} to {BUCKET}"}), 200

@app.route("/list")
def list_files():
    response = s3.list_objects_v2(Bucket=BUCKET)
    files = [obj["Key"] for obj in response.get("Contents", [])]
    return jsonify(files)

@app.route("/download/<path:filename>")
def download(filename):
    obj = s3.get_object(Bucket=BUCKET, Key=filename)
    return send_file(io.BytesIO(obj["Body"].read()), download_name=filename, as_attachment=True)

# === AI Detection Threshold Endpoints ===

@app.route("/thresholds", methods=["GET"])
def get_thresholds():
    """Get current detection thresholds"""
    class_mapping = {
        0: "person",
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
        63: "laptop"
    }

    thresholds = {}
    for cls_id, cls_name in class_mapping.items():
        threshold = detector.class_thresholds.get(cls_id, detector.conf_threshold)
        thresholds[cls_name] = int(threshold * 100)

    return jsonify(thresholds)

@app.route("/thresholds", methods=["POST"])
def update_thresholds():
    """Update detection thresholds"""
    try:
        data = request.get_json()

        # Map class names to IDs
        name_to_id = {
            "person": 0,
            "car": 2,
            "motorcycle": 3,
            "bus": 5,
            "truck": 7,
            "laptop": 63
        }

        # Update thresholds
        for cls_name, threshold_pct in data.items():
            if cls_name in name_to_id:
                cls_id = name_to_id[cls_name]
                detector.class_thresholds[cls_id] = threshold_pct / 100.0

        # Print new thresholds
        print("\n🎯 Detection thresholds updated:")
        for cls_id, cls_name in detector.class_names.items():
            threshold = detector.class_thresholds.get(cls_id, detector.conf_threshold)
            print(f"   - {cls_name}: {int(threshold * 100)}%")

        return jsonify({
            "message": "Thresholds updated successfully",
            "thresholds": data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Debug Endpoints ===

@app.route("/debug/config", methods=["GET"])
def debug_config():
    """Debug endpoint to show camera configuration and system state"""
    try:
        config_info = {
            "config_file": camera_manager.config_file,
            "config_exists": os.path.exists(camera_manager.config_file),
            "cameras_in_memory": list(camera_manager.cameras.keys()),
            "cameras_in_config": []
        }

        # Read config file if it exists
        if config_info["config_exists"]:
            try:
                with open(camera_manager.config_file, 'r') as f:
                    config_data = json.load(f)
                    config_info["cameras_in_config"] = [
                        {
                            "camera_id": c.get("camera_id"),
                            "stream_url": c.get("stream_url")
                        }
                        for c in config_data.get("cameras", [])
                    ]
                    config_info["config_file_contents"] = config_data
            except Exception as e:
                config_info["config_read_error"] = str(e)

        return jsonify(config_info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug/performance", methods=["GET"])
def debug_performance():
    """Performance monitoring endpoint"""
    try:
        import torch
        import psutil

        perf_info = {
            "gpu": {
                "available": torch.cuda.is_available(),
                "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
                "current_device": torch.cuda.current_device() if torch.cuda.is_available() else None,
                "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            },
            "model": {
                "type": detector.model_type,
                "path": detector.model_path,
                "avg_inference_ms": round(sum(detector.inference_times) / len(detector.inference_times), 1) if detector.inference_times else 0,
                "total_detections": detector.total_detections
            },
            "cameras": {},
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": round(psutil.virtual_memory().available / 1024 / 1024)
            }
        }

        # Add per-camera performance stats
        for cam_id, cam in camera_manager.cameras.items():
            perf_info["cameras"][cam_id] = {
                "fps": round(cam.current_fps, 1),
                "avg_inference_ms": cam.stats.get('avg_inference_ms', 0),
                "frames_processed": cam.stats['frames_processed'],
                "detections": cam.stats['detections'],
                "detection_interval": cam.detection_interval,
                "inference_resolution": cam.inference_resolution,
                "status": cam.stats['status']
            }

        return jsonify(perf_info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Update System Endpoints ===

@app.route("/update/check", methods=["GET"])
def check_update():
    """Check if updates are available from GitHub"""
    try:
        # Get latest commit hash from GitHub
        github_api_url = "https://api.github.com/repos/espressojuice/dealereye/commits/main"
        response = requests.get(github_api_url, timeout=5)

        if response.status_code != 200:
            return jsonify({
                "error": "Failed to check GitHub",
                "update_available": False
            }), 500

        github_commit = response.json()['sha'][:7]  # Short hash

        # Get local commit hash
        # Try /app first (container path), fall back to /opt/dealereye (host path)
        local_commit = "unknown"
        for git_dir in ['/app', '/opt/dealereye']:
            try:
                result = subprocess.run(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=git_dir,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    local_commit = result.stdout.strip()
                    print(f"[Update] Local commit from {git_dir}: {local_commit}")
                    break
            except Exception as e:
                print(f"[Update] Failed to get git hash from {git_dir}: {e}")
                continue

        update_available = github_commit != local_commit and local_commit != "unknown"

        print(f"[Update] GitHub: {github_commit}, Local: {local_commit}, Update available: {update_available}")

        return jsonify({
            "update_available": update_available,
            "local_version": local_commit,
            "latest_version": github_commit,
            "update_command": "curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash"
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "update_available": False
        }), 500

@app.route("/update/apply", methods=["POST"])
def apply_update():
    """Trigger system update"""
    try:
        # Write update trigger file that host script can detect
        trigger_file = "/app/config/.update_trigger"

        try:
            with open(trigger_file, 'w') as f:
                f.write(f"update_requested_at={datetime.now().isoformat()}\n")

            return jsonify({
                "message": "Update triggered! System will restart in a few seconds...",
                "status": "triggered"
            })
        except Exception as ex:
            # If we can't write trigger file, return manual instructions
            return jsonify({
                "message": "Please run the following command on your Jetson to update:",
                "command": "curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash",
                "status": "manual",
                "error": str(ex)
            })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "status": "error"
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
