# Base image optimized for NVIDIA Jetson with GPU support
# Use NVIDIA L4T (Linux for Tegra) base image for best Jetson performance
# R36 = JetPack 6.x (for Orin with driver 540.x and CUDA 12.x)
# l4t-ml includes PyTorch, TensorFlow, and other ML frameworks
FROM nvcr.io/nvidia/l4t-ml:r36.2.0-py3

# Install additional dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg git curl wget && \
    rm -rf /var/lib/apt/lists/*

# Copy app files
WORKDIR /app
COPY . /app

# Make update script executable
RUN chmod +x /app/update.sh

# Install Python packages (PyTorch already included in base image with CUDA support)
# l4t-ml base image already includes opencv, numpy, and other ML libraries
# Just install our application dependencies
RUN pip3 install --no-cache-dir \
    boto3 \
    flask \
    requests \
    pillow \
    'ultralytics<8.3' \
    psutil

# Create config directory for persistent camera settings
RUN mkdir -p /app/config

# Expose Flask port
EXPOSE 8080

# Run the app
CMD ["python3", "app.py"]
