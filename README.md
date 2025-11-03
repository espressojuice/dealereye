# Dealereye - AI-Powered Video Security for Dealerships

Edge AI system for car dealerships featuring YOLOv8 object detection, RTSP camera support, and cloud storage integration.

## Features

- **Real-time AI Detection**: YOLOv8 inference on Jetson hardware
- **Multi-Camera Support**: Monitor multiple RTSP/IP cameras simultaneously
- **Auto-Recording**: Automatically captures clips when people/vehicles detected
- **Cloud Storage**: Automatic upload to Wasabi S3
- **RESTful API**: Full control via HTTP endpoints
- **Edge Processing**: All AI runs locally on Jetson device

## Hardware Requirements

- NVIDIA Jetson Orin NX / Xavier / Nano
- Ubuntu 20.04/22.04 or JetPack
- IP cameras with RTSP support
- Internet connection for cloud uploads

## Quick Start

### 1. Install on Jetson

```bash
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash
```

The installer will:
- Install Docker if needed
- Clone/update the repository
- Build and start the container with **GPU acceleration**
- Auto-optimize YOLOv8 with TensorRT (5-10x speedup)
- Print the local access URL

### 2. Access the Dashboard

```
http://<JETSON_IP>:8080/dashboard
```

## ⚡ Performance Optimization

Dealereye is optimized for NVIDIA Jetson with multiple performance tuning options:

### GPU Acceleration (Enabled by Default)
- Uses NVIDIA L4T base image with CUDA support
- Runs with `--runtime nvidia --gpus all` flags
- TensorRT optimization for 5-10x faster inference
- All AI processing runs on Jetson GPU, not CPU

### Performance Tuning Options

**Option 1: Environment Variables (Recommended)**
```bash
# Faster processing, fewer detections (good for high FPS cameras)
DETECTION_INTERVAL=10 INFERENCE_WIDTH=640 curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash

# Balanced (default)
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash

# Maximum accuracy, slower (good for critical areas)
DETECTION_INTERVAL=1 curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash
```

**Available Settings:**
- `DETECTION_INTERVAL`: Run AI every N frames (default: 5)
  - Higher = faster processing, fewer detections
  - Lower = more detections, slower processing
  - Recommended: 5-10 for most use cases

- `INFERENCE_WIDTH`: Resize frames for AI (default: full resolution)
  - 640 = 2-3x speedup with minimal accuracy loss
  - 0 = full resolution (slowest, most accurate)
  - Recommended: 640 for 1080p+ cameras

**Option 2: Monitor Performance**
```bash
# Check GPU usage, inference times, FPS
curl http://<JETSON_IP>:8080/debug/performance | jq
```

Example output:
```json
{
  "gpu": {
    "available": true,
    "device_name": "Orin NX",
    "device_count": 1
  },
  "model": {
    "type": "TensorRT",
    "avg_inference_ms": 15.3
  },
  "cameras": {
    "Backyard": {
      "fps": 28.5,
      "avg_inference_ms": 15.3,
      "detection_interval": 5,
      "inference_resolution": 640
    }
  }
}
```

### Expected Performance

**With GPU + TensorRT:**
- YOLOv8n @ 640px: **15-25ms per inference** (40-65 FPS)
- YOLOv8n @ 1080p: **40-60ms per inference** (16-25 FPS)
- Multiple cameras: Process 3-5 streams simultaneously

**Without GPU (CPU only):**
- YOLOv8n @ 640px: ~200-300ms per inference (3-5 FPS)
- ❌ **Not recommended for production use**

### Camera Stream Optimization

For best performance, use **substream** from your NVR/camera:
- Main stream: 1080p @ 30fps → Heavy on network and processing
- Sub stream: 720p @ 15fps → Much faster, still accurate

Example with Digital Watchdog Spectrum:
```bash
# Main stream (slower)
rtsp://admin:pass@192.168.1.2:7001/<camera_id>?stream=0

# Sub stream (faster) ✅ Recommended
rtsp://admin:pass@192.168.1.2:7001/<camera_id>?stream=1
```

## API Endpoints

### System Status

```bash
GET /
# Returns system status and camera list
```

### Camera Management

**List all cameras:**
```bash
GET /cameras
```

**Add a camera:**
```bash
POST /cameras
Content-Type: application/json

{
  "camera_id": "front_gate",
  "stream_url": "rtsp://192.168.1.100:554/stream"
}
```

**Start/Stop camera:**
```bash
POST /cameras/{camera_id}/start
POST /cameras/{camera_id}/stop
```

**Remove camera:**
```bash
DELETE /cameras/{camera_id}
```

### Detection & Monitoring

**Get camera statistics:**
```bash
GET /cameras/{camera_id}/stats
```

**Get latest detections:**
```bash
GET /cameras/{camera_id}/detections
```

**View live snapshot (JPEG):**
```bash
GET /cameras/{camera_id}/snapshot
```

**Save snapshot with detections:**
```bash
POST /cameras/{camera_id}/snapshot/save
# Saves locally and uploads to Wasabi
```

### Video Recording

**Record a clip:**
```bash
POST /cameras/{camera_id}/record
Content-Type: application/json

{
  "duration": 10  # seconds
}
```

**Upload clip to Wasabi:**
```bash
POST /clips/upload/<filepath>
```

### Storage (Wasabi S3)

**Upload file:**
```bash
POST /upload
Content-Type: multipart/form-data
file=@video.mp4
```

**List files:**
```bash
GET /list
```

**Download file:**
```bash
GET /download/{filename}
```

## TensorRT Optimization (Jetson GPU Acceleration)

### Why TensorRT?

TensorRT provides **3-5x faster inference** on Jetson hardware compared to PyTorch:
- YOLOv8n PyTorch: ~40-60ms per frame
- YOLOv8n TensorRT: ~10-15ms per frame
- Enables real-time processing of multiple cameras

### Optimize Your Model

**On the Jetson device**, run the optimization script:

```bash
# SSH into your Jetson
ssh jetson@<JETSON_IP>

# Navigate to installation
cd /opt/dealereye

# Optimize the model (takes 5-10 minutes)
python3 optimize_model.py --model yolov8n.pt --half --benchmark

# This creates yolov8n.engine in the same directory
```

**Options:**
```bash
python3 optimize_model.py \
  --model yolov8n.pt \      # Model to optimize
  --imgsz 640 \              # Input size (640 recommended)
  --half \                   # Use FP16 precision (faster, recommended)
  --workspace 4 \            # GPU memory in GB
  --benchmark \              # Test performance after export
  --compare                  # Compare PyTorch vs TensorRT speed
```

**Model variants:**
- `yolov8n.pt` - Nano (fastest, recommended for Jetson Nano/Xavier)
- `yolov8s.pt` - Small (good balance)
- `yolov8m.pt` - Medium (best accuracy, requires Orin)

### Using TensorRT Engine

The system **automatically detects** and uses `.engine` files:

1. After running `optimize_model.py`, restart the container:
   ```bash
   sudo docker restart dealereye
   ```

2. Check the logs to confirm TensorRT is active:
   ```bash
   sudo docker logs dealereye
   # Should show: "🚀 TensorRT engine found: yolov8n.engine"
   ```

3. Monitor performance:
   ```bash
   curl http://localhost:8080/performance
   ```

**Performance API response:**
```json
{
  "model_type": "TensorRT",
  "avg_inference_ms": 12.5,
  "fps": 80.0,
  "min_inference_ms": 10.2,
  "max_inference_ms": 15.8
}
```

### Troubleshooting TensorRT

**"Failed to build engine":**
- Reduce workspace: `--workspace 2`
- Use FP32: remove `--half` flag
- Check available GPU memory: `tegrastats`

**Engine file not detected:**
- Ensure `.engine` file is in same directory as `.pt` file
- Check file permissions: `ls -l *.engine`
- Restart container after creating engine

**Slower than expected:**
- Verify GPU is being used: `tegrastats` (GPU usage should be >0%)
- Check power mode: `sudo nvpmodel -q` (should be MAXN)
- Ensure FP16 was used during export

## Configuration

### Wasabi Credentials

Create `~/.aws/credentials` on the Jetson:

```ini
[default]
aws_access_key_id = YOUR_KEY
aws_secret_access_key = YOUR_SECRET
```

### Detection Settings

Edit `app.py` to adjust:
- `conf_threshold`: Detection confidence (default: 0.5)
- `model_path`: YOLOv8 model variant (yolov8n/s/m/l/x)

Edit `camera.py` to adjust:
- `detection_interval`: Run detection every N frames (default: 5)
- `frame_buffer`: Pre-event buffer size (default: 150 frames)
- `clip duration`: Auto-recording length (default: 10s)

## Testing

### Test with Sample Video

```python
import requests

# Add a camera (use video file for testing)
response = requests.post('http://localhost:8080/cameras', json={
    'camera_id': 'test_cam',
    'stream_url': '/path/to/test_video.mp4'
})

# Start the camera
requests.post('http://localhost:8080/cameras/test_cam/start')

# Check detections
response = requests.get('http://localhost:8080/cameras/test_cam/detections')
print(response.json())

# Get a snapshot
response = requests.get('http://localhost:8080/cameras/test_cam/snapshot')
with open('snapshot.jpg', 'wb') as f:
    f.write(response.content)
```

### Test with RTSP Camera

```bash
# Add camera
curl -X POST http://localhost:8080/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "front_gate",
    "stream_url": "rtsp://admin:password@192.168.1.100:554/stream"
  }'

# Start camera
curl -X POST http://localhost:8080/cameras/front_gate/start

# Check status
curl http://localhost:8080/cameras/front_gate/stats
```

## Architecture

```
[IP Cameras] → [RTSP Streams]
                    ↓
    [Camera Manager (multi-threaded)]
                    ↓
    [YOLOv8 + TensorRT (Jetson GPU)]
                    ↓
         [Detection Events]
          /              \
    [Local Storage]    [Wasabi S3]
         ↓
    [Flask API] → [Remote Dashboard]
```

## File Structure

```
dealereye/
├── app.py          # Flask API server
├── detector.py     # YOLOv8 inference module
├── camera.py       # RTSP stream handler
├── Dockerfile      # Container definition
├── install.sh      # Auto-installer script
├── snapshots/      # Detection snapshots
└── clips/          # Video clips
```

## Performance Tips

1. **Use TensorRT**: Run `optimize_model.py` for 3-5x faster inference (see TensorRT section)
2. **Model Selection**: Use `yolov8n.pt` for best speed, `yolov8s.pt` for better accuracy
3. **Resolution**: Reduce camera resolution if needed (720p recommended)
4. **Detection Interval**: Increase if CPU maxed out (e.g., every 10 frames)
5. **Power Mode**: Set Jetson to max performance: `sudo nvpmodel -m 0`
6. **Multiple Cameras**: With TensorRT, Orin can handle 4-8 cameras simultaneously

**Expected Performance (Jetson Orin NX with TensorRT):**
- YOLOv8n: ~80 FPS (12ms per frame)
- YOLOv8s: ~50 FPS (20ms per frame)
- 4 cameras @ 720p: ~20-25 FPS per camera

## Troubleshooting

**Camera won't connect:**
- Verify RTSP URL with VLC or ffplay
- Check network connectivity
- Ensure camera supports RTSP

**Detection not working:**
- Check model downloaded: `yolov8n.pt` should appear in container
- View logs: `docker logs dealereye`

**High CPU usage:**
- Increase `detection_interval` in camera.py
- Use smaller YOLOv8 model (nano)
- Reduce camera resolution

**Clips not uploading:**
- Verify Wasabi credentials in `~/.aws/credentials`
- Check bucket name matches in app.py
- Test upload manually via `/upload` endpoint

## Updates

Pull latest code and rebuild:

```bash
cd /opt/dealereye
sudo git pull
sudo docker stop dealereye
sudo docker rm dealereye
sudo docker build -t dealereye .
sudo docker run -d --restart unless-stopped -p 8080:8080 --name dealereye -v ~/.aws:/root/.aws dealereye
```

Or just re-run the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/espressojuice/dealereye/main/install.sh | bash
```

## License

MIT

## Support

Issues: https://github.com/espressojuice/dealereye/issues
