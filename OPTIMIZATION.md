# Dealereye Optimization Guide

Complete guide to maximizing performance on NVIDIA Jetson hardware.

## Table of Contents

1. [TensorRT Optimization](#tensorrt-optimization)
2. [Jetson Power Configuration](#jetson-power-configuration)
3. [Multi-Camera Scaling](#multi-camera-scaling)
4. [Performance Benchmarking](#performance-benchmarking)
5. [Common Issues & Solutions](#common-issues--solutions)

---

## TensorRT Optimization

### Overview

TensorRT is NVIDIA's high-performance inference optimizer. It provides:
- **3-5x faster inference** compared to PyTorch
- **Lower power consumption**
- **Better multi-camera support**

### Step-by-Step Optimization

#### 1. Prepare Your Jetson

```bash
# SSH into Jetson
ssh jetson@<JETSON_IP>

# Check CUDA/TensorRT installation
nvcc --version
dpkg -l | grep tensorrt

# Navigate to Dealereye
cd /opt/dealereye
```

#### 2. Choose Your Model

| Model | Speed | Accuracy | Best For |
|-------|-------|----------|----------|
| yolov8n.pt | Fastest | Good | Nano, Xavier, 4+ cameras |
| yolov8s.pt | Fast | Better | Orin, 2-4 cameras |
| yolov8m.pt | Medium | Best | Orin only, 1-2 cameras |

**Recommendation for dealerships:** `yolov8n.pt` provides excellent detection while supporting the most cameras.

#### 3. Run Optimization

```bash
# Basic optimization (recommended)
python3 optimize_model.py --model yolov8n.pt --half

# With benchmarking
python3 optimize_model.py --model yolov8n.pt --half --benchmark

# Compare PyTorch vs TensorRT
python3 optimize_model.py --model yolov8n.pt --half --compare
```

**Expected output:**
```
==============================================================
TensorRT Model Export for Jetson
==============================================================

1. Loading model: yolov8n.pt

2. Exporting to TensorRT...
   - Image size: 640
   - Precision: FP16
   - Workspace: 4GB

   This may take several minutes...

✅ Export complete!
   TensorRT engine: yolov8n.engine
   File size: 12.5 MB
```

#### 4. Restart & Verify

```bash
# Restart container to load new engine
sudo docker restart dealereye

# Check logs
sudo docker logs dealereye | grep TensorRT
# Should show: "🚀 TensorRT engine found: yolov8n.engine"

# Test performance
curl http://localhost:8080/performance
```

#### 5. Performance Validation

Expected metrics after TensorRT optimization:

**Jetson Orin NX:**
- Inference time: 10-15ms
- FPS: 60-80
- Multiple cameras: 4-8 streams @ 720p

**Jetson Xavier NX:**
- Inference time: 20-30ms
- FPS: 30-50
- Multiple cameras: 2-4 streams @ 720p

**Jetson Nano:**
- Inference time: 50-80ms
- FPS: 12-20
- Multiple cameras: 1-2 streams @ 720p

---

## Jetson Power Configuration

### Check Current Mode

```bash
# View current power mode
sudo nvpmodel -q

# View available modes
sudo nvpmodel -p --verbose
```

### Set Maximum Performance

```bash
# Jetson Orin - MAXN mode
sudo nvpmodel -m 0

# Enable max clock speeds
sudo jetson_clocks

# Verify
sudo jetson_clocks --show
```

### Power Modes Comparison

| Device | Mode | Power | Performance |
|--------|------|-------|-------------|
| Orin NX | MAXN (0) | 25W | 100% |
| Orin NX | 15W (1) | 15W | ~70% |
| Orin NX | 10W (2) | 10W | ~50% |

**Recommendation:** Use MAXN (mode 0) for production deployments with active cooling.

### Monitor Power & Temperature

```bash
# Real-time monitoring
tegrastats

# Key metrics to watch:
# - CPU/GPU usage
# - RAM usage
# - Temperature (keep under 80°C)
```

---

## Multi-Camera Scaling

### Configuration for Multiple Cameras

#### Adjust Detection Interval

Edit `camera.py` line 134:

```python
# For 1-2 cameras (highest quality)
detection_interval = 3  # Run AI every 3 frames

# For 3-4 cameras (balanced)
detection_interval = 5  # Run AI every 5 frames (default)

# For 5+ cameras (maximum throughput)
detection_interval = 10  # Run AI every 10 frames
```

#### Optimize Frame Buffer

Edit `camera.py` line 38:

```python
# Default: 150 frames (~5 seconds @ 30fps)
self.frame_buffer = deque(maxlen=150)

# For more cameras, reduce buffer
self.frame_buffer = deque(maxlen=90)  # ~3 seconds
```

### Recommended Camera Limits

| Jetson Model | With TensorRT | Without TensorRT |
|--------------|---------------|------------------|
| Orin NX 16GB | 6-8 cameras | 2-3 cameras |
| Xavier NX 8GB | 3-4 cameras | 1-2 cameras |
| Nano 4GB | 1-2 cameras | 1 camera |

**All at 720p resolution, 30 FPS**

### Load Balancing

For 8+ cameras, use **multiple Jetson devices**:

```
Front Lot (4 cameras) → Jetson #1
Back Lot (4 cameras) → Jetson #2
Service Area (2 cameras) → Jetson #3
```

Aggregate data via central dashboard (future feature).

---

## Performance Benchmarking

### Quick Benchmark

```bash
# Benchmark current setup
curl http://localhost:8080/performance

# Example response:
{
  "model_type": "TensorRT",
  "avg_inference_ms": 12.5,
  "fps": 80.0,
  "min_inference_ms": 10.2,
  "max_inference_ms": 15.8,
  "total_inferences": 1000,
  "total_detections": 247
}
```

### Full Performance Test

```python
import requests
import time

base_url = "http://localhost:8080"

# Add test camera
requests.post(f"{base_url}/cameras", json={
    "camera_id": "perf_test",
    "stream_url": "rtsp://your-test-camera"
})

# Start camera
requests.post(f"{base_url}/cameras/perf_test/start")

# Let it run for 60 seconds
print("Running performance test for 60 seconds...")
time.sleep(60)

# Get results
stats = requests.get(f"{base_url}/cameras/perf_test/stats").json()
perf = requests.get(f"{base_url}/performance").json()

print(f"Frames processed: {stats['frames_processed']}")
print(f"Detections: {stats['detections']}")
print(f"Average FPS: {perf['fps']}")
print(f"Average inference: {perf['avg_inference_ms']}ms")

# Cleanup
requests.delete(f"{base_url}/cameras/perf_test")
```

### Metrics to Monitor

**Inference Performance:**
- Target: <20ms per frame (TensorRT)
- Warning: >30ms (consider reducing load)
- Critical: >50ms (reduce cameras or resolution)

**System Resources:**
```bash
# Monitor GPU usage
tegrastats | grep GR3D

# Target: 60-80% GPU usage
# If <50%: CPU bottleneck, reduce detection interval
# If >90%: GPU maxed, reduce cameras or model size
```

---

## Common Issues & Solutions

### Issue: Slow Inference (>50ms)

**Diagnosis:**
```bash
curl http://localhost:8080/performance
# Check model_type
```

**Solutions:**
1. Verify TensorRT is active: `model_type` should be `"TensorRT"`
2. If PyTorch: Run `optimize_model.py`
3. Check power mode: `sudo nvpmodel -q` (should be mode 0)
4. Reduce model size: yolov8m → yolov8s → yolov8n

### Issue: TensorRT Export Fails

**Error:** "Failed to build engine"

**Solutions:**
```bash
# 1. Reduce workspace memory
python3 optimize_model.py --model yolov8n.pt --workspace 2

# 2. Use FP32 instead of FP16
python3 optimize_model.py --model yolov8n.pt

# 3. Check GPU memory
free -h
# Ensure >2GB free RAM

# 4. Verify CUDA/TensorRT
jtop  # Install with: sudo -H pip install jetson-stats
```

### Issue: Multiple Cameras Lagging

**Symptoms:**
- High frame drop rate
- Detections delayed
- CPU/GPU at 100%

**Solutions:**
1. Increase detection interval (camera.py line 134)
2. Reduce camera resolution to 720p
3. Optimize with TensorRT if not already done
4. Reduce concurrent cameras
5. Decrease frame buffer size

### Issue: Out of Memory

**Error:** "CUDA out of memory" or system freeze

**Solutions:**
```bash
# 1. Check memory usage
free -h

# 2. Reduce TensorRT workspace
python3 optimize_model.py --model yolov8n.pt --workspace 1

# 3. Reduce frame buffers in camera.py
# Change line 38: deque(maxlen=60)  # Was 150

# 4. Limit concurrent cameras
# Remove cameras via API: DELETE /cameras/{id}

# 5. Restart container to free memory
sudo docker restart dealereye
```

### Issue: Engine Not Detected After Export

**Symptoms:**
- Logs show "Using PyTorch model"
- No "TensorRT engine found" message

**Solutions:**
```bash
# 1. Verify .engine file exists
ls -lh *.engine

# 2. Check file is in correct location
# Should be same directory as .pt file

# 3. Check file permissions
chmod 644 *.engine

# 4. Restart container
sudo docker restart dealereye

# 5. Check container mounts
sudo docker inspect dealereye | grep -A 10 Mounts
```

---

## Advanced: Custom Optimization

### Fine-Tune for Your Environment

#### Lighting Conditions

```python
# Edit detector.py line 37 (in container or before build)

# Bright outdoor (parking lots)
conf_threshold = 0.6  # Higher = fewer false positives

# Mixed indoor/outdoor
conf_threshold = 0.5  # Default, balanced

# Low light (night)
conf_threshold = 0.4  # Lower = catch more objects
```

#### Detection Classes

To detect only people (ignore vehicles):

```python
# Edit detector.py lines 49-56
self.target_classes = [0]  # Only person
self.class_names = {0: "person"}
```

To add more vehicle types:

```python
# COCO classes: 1=bicycle, 2=car, 3=motorcycle, 4=airplane,
#               5=bus, 6=train, 7=truck, 8=boat
self.target_classes = [0, 1, 2, 3, 5, 7, 8]  # Added bicycle, boat
```

### Build Optimized Dockerfile

For production deployments, pre-build with TensorRT:

```dockerfile
# Add to Dockerfile after COPY . /app

# Download and optimize model during build
RUN python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
RUN python3 optimize_model.py --model yolov8n.pt --half || true
```

---

## Summary Checklist

Before deploying to production:

- [ ] TensorRT model exported and tested
- [ ] Jetson set to MAXN power mode
- [ ] `jetson_clocks` enabled
- [ ] Performance benchmarked (target >60 FPS)
- [ ] Multiple cameras tested simultaneously
- [ ] Temperature monitoring setup (tegrastats)
- [ ] Detection interval optimized for camera count
- [ ] Memory usage verified (<80% RAM usage)
- [ ] Auto-restart enabled (Docker flag: `--restart unless-stopped`)

---

## Getting Help

**Performance Issues:**
1. Check `/performance` API endpoint
2. Run `tegrastats` for 30 seconds
3. Collect logs: `sudo docker logs dealereye > logs.txt`
4. Open issue with metrics

**GitHub Issues:** https://github.com/espressojuice/dealereye/issues
