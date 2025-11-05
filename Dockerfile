# Base image optimized for NVIDIA Jetson with GPU support
# Use NVIDIA L4T (Linux for Tegra) base image for best Jetson performance
# R35 = JetPack 5.x - using this as R36 has opencv conflicts with ultralytics
FROM nvcr.io/nvidia/l4t-pytorch:r35.2.1-pth2.0-py3

# Install additional dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg git curl wget build-essential && \
    rm -rf /var/lib/apt/lists/*

# Build libffi 3.4.2 from source to provide libffi.so.8 (required by newer opencv-python)
RUN cd /tmp && \
    wget https://github.com/libffi/libffi/releases/download/v3.4.2/libffi-3.4.2.tar.gz && \
    tar -xzf libffi-3.4.2.tar.gz && \
    cd libffi-3.4.2 && \
    ./configure --prefix=/usr && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf /tmp/libffi-3.4.2*

# Copy app files
WORKDIR /app
COPY . /app

# Make update script executable
RUN chmod +x /app/update.sh

# Install Python packages (PyTorch already included in base image with CUDA support)
# Upgrade numpy first (base image has 1.17.4, ultralytics needs >=1.23.0)
# Pin ultralytics to version that works on Jetson ARM
# Install opencv and remove problematic modules, use waitress for production server
RUN pip3 install --no-cache-dir --upgrade 'numpy>=1.23.0,<2.0.0' && \
    pip3 install --no-cache-dir \
    'opencv-python-headless==4.5.1.48' \
    boto3 \
    flask \
    waitress \
    requests \
    pillow \
    'ultralytics<8.3' \
    psutil && \
    find /usr/local/lib -name cv2 -type d -exec rm -rf {}/gapi {}/mat_wrapper \; 2>/dev/null || true

# Create config directory for persistent camera settings
RUN mkdir -p /app/config

# Expose Flask port
EXPOSE 8080

# Run the app
CMD ["python3", "app.py"]
