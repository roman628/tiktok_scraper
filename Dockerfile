# Multi-stage build for faster rebuilds
# Stage 1: Base with all heavy dependencies (cached)
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS base

# Set environment to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Mark this as a Docker container for Python path detection
ENV DOCKER_CONTAINER=1

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

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install PyTorch with CUDA support first (heaviest, changes least)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Copy only requirements file (not code yet)
COPY requirements.txt .

# Install remaining Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download models and data
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('vader_lexicon', quiet=True)" || true && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# Stage 2: Final image with application code  
# This stage only rebuilds when code changes
FROM base AS final

WORKDIR /app

# Copy only application code (this layer rebuilds on code changes)
COPY . .

# Ensure config.toml exists (create from template if missing)
RUN if [ ! -f /app/config.toml ] || [ -d /app/config.toml ]; then \
        rm -rf /app/config.toml && \
        cp /app/assets/config.template.toml /app/config.toml; \
    fi

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