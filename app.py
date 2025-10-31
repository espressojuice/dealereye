from flask import Flask, request, jsonify, send_file, Response
import boto3
import os
import io
import cv2
from detector import Detector
from camera import CameraManager

app = Flask(__name__)

BUCKET = "dealereye"
ENDPOINT = "https://s3.us-east-1.wasabisys.com"

s3 = boto3.client("s3", endpoint_url=ENDPOINT)

# Initialize AI detector and camera manager
print("Initializing Dealereye AI system...")
detector = Detector(model_path="yolov8n.pt", conf_threshold=0.5)
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

    if not data or "camera_id" not in data or "stream_url" not in data:
        return jsonify({"error": "camera_id and stream_url required"}), 400

    camera = camera_manager.add_camera(data["camera_id"], data["stream_url"])
    return jsonify({"message": f"Camera {data['camera_id']} added", "camera": camera.get_stats()})

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
    """Remove a camera"""
    if camera_manager.remove_camera(camera_id):
        return jsonify({"message": f"Camera {camera_id} removed"})
    return jsonify({"error": f"Camera {camera_id} not found"}), 404

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
