# Use official NVIDIA CUDA base image with cuDNN 9 - optimal for faster-whisper
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install playwright browsers for TikTokApi
RUN playwright install chromium
RUN playwright install-deps

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p ./assets ./downloads

# Set environment variables for CUDA
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV CUDA_VISIBLE_DEVICES=all

# Set Python path
ENV PYTHONPATH=/app

# Default command runs main.py
CMD ["python3", "main.py"]