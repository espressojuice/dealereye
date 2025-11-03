# Base image optimized for NVIDIA Jetson with GPU support
# Use NVIDIA L4T (Linux for Tegra) base image for best Jetson performance
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
# Pin ultralytics to version that works on Jetson ARM (newer versions have polars dependency issues)
# Pin opencv-python to version stable on Jetson ARM with Python 3.8
RUN pip3 install --no-cache-dir \
    'opencv-python-headless==4.5.5.64' \
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
