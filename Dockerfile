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

# Install Python packages (PyTorch already included in base image with CUDA support)
RUN pip3 install --no-cache-dir \
    boto3 \
    flask \
    requests \
    pillow \
    ultralytics \
    opencv-python \
    numpy \
    psutil

# Create config directory for persistent camera settings
RUN mkdir -p /app/config

# Expose Flask port
EXPOSE 8080

# Run the app
CMD ["python3", "app.py"]
