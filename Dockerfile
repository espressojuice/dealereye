# Base image with Python and Jetson libraries
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-pip ffmpeg git curl && \
    rm -rf /var/lib/apt/lists/*

# Copy app files
WORKDIR /app
COPY . /app

# Install Python packages
RUN pip3 install --no-cache-dir boto3 flask requests pillow

# Expose Flask port
EXPOSE 8080

# Run the app
CMD ["python3", "app.py"]
