# Base image optimized for NVIDIA Jetson with GPU support
# Use NVIDIA L4T (Linux for Tegra) base image for best Jetson performance
FROM nvcr.io/nvidia/l4t-pytorch:r35.2.1-pth2.0-py3

# Install additional dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy app files
WORKDIR /app
COPY . /app

# Make update script executable
RUN chmod +x /app/update.sh

# Install Python packages (PyTorch already included in base image with CUDA support)
# Pin ultralytics to version that works on Jetson ARM (newer versions have polars dependency issues)
# Install opencv-python-headless FIRST to prevent ultralytics from installing opencv-python
# (headless version avoids GUI library conflicts with NVIDIA drivers)
# Pin to version compatible with Ubuntu 20.04 (libffi.so.7)
RUN pip3 install --no-cache-dir 'opencv-python-headless<4.6.0' && \
    pip3 install --no-cache-dir \
    boto3 \
    flask \
    requests \
    pillow \
    'ultralytics<8.3' \
    numpy \
    psutil

# Create config directory for persistent camera settings
RUN mkdir -p /app/config

# Expose Flask port
EXPOSE 8080

# Run the app
CMD ["python3", "app.py"]
