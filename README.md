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
- Build and start the container
- Print the local access URL

### 2. Access the Dashboard

```
http://<JETSON_IP>:8080/
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

1. **Model Selection**: Use `yolov8n.pt` for best speed on Jetson Nano/Xavier
2. **Resolution**: Reduce camera resolution if needed (720p recommended)
3. **Detection Interval**: Increase if CPU maxed out (e.g., every 10 frames)
4. **Multiple Cameras**: Test 2-3 cameras first, then scale based on performance

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
