# TikTok Scraper - Base Multi-Service Dockerfile
# Optimized for ML, browser automation, and data processing

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    gcc \
    g++ \
    cmake \
    pkg-config \
    # System libraries
    libffi-dev \
    libssl-dev \
    libbz2-dev \
    liblzma-dev \
    libsqlite3-dev \
    # Media processing
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    # Browser automation
    wget \
    gnupg \
    unzip \
    xvfb \
    # Chrome dependencies
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Chrome browser for Selenium
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN pip install playwright==1.53.0 \
    && playwright install chromium \
    && playwright install-deps

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt ./
COPY keyword_scoring_system/requirements.txt ./keyword_scoring_requirements.txt
COPY tiktok_insights/requirements.txt ./insights_requirements.txt
COPY reddit_scraper/requirements.txt ./reddit_requirements.txt
COPY performance_predictor/predictor_requirements.txt ./predictor_requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install -r keyword_scoring_requirements.txt \
    && pip install -r insights_requirements.txt \
    && pip install -r reddit_requirements.txt \
    && pip install -r predictor_requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('vader_lexicon'); nltk.download('stopwords')"

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Create app directories
RUN mkdir -p /app/data /app/downloads /app/models /app/outputs /app/backups /app/logs

# Copy application code
COPY . .

# Set permissions
RUN chmod +x /app/main.py && \
    chmod +x /app/docker-entrypoint.sh

# Expose ports
EXPOSE 8000 8080

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command
CMD ["python", "main.py"]