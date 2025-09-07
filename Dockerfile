# Single Dockerfile supporting both CPU and GPU with CUDA
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Set environment to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 and system dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    python3-pip \
    ffmpeg \
    postgresql-client \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install PyTorch with CUDA support first (will work on CPU too)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining Python packages (excluding torch to avoid conflicts)
RUN pip install --no-cache-dir -r requirements.txt --no-deps torch || \
    pip install --no-cache-dir -r requirements.txt

# Pre-download models and data
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('vader_lexicon', quiet=True)" || true && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p \
    data \
    downloads \
    logs \
    ml/models \
    ml/data \
    media/previews \
    database \
    /app/nltk_data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=tiktok_scraper.settings
ENV NLTK_DATA=/app/nltk_data

# Make scripts executable
RUN chmod +x manage.py || true
RUN chmod +x collector.py || true
RUN chmod +x extension/start_server.sh || true

# Expose ports
EXPOSE 8000 8080

# Default command - run Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]