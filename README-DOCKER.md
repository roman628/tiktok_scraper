# 🐳 TikTok Scraper Docker Documentation

Complete dockerization of the TikTok Research & Analysis Suite with multi-service architecture, browser automation, and ML model support.

## 🚀 Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 8GB RAM (for ML models)
- 10GB free disk space

### 1. Build and Start All Services
```bash
# Build containers
docker-compose build

# Start all services
./docker-scripts/start-services.sh all

# Check status
./docker-scripts/start-services.sh status
```

### 2. Access Services
- **Selenium Hub**: http://localhost:4444
- **Performance Predictor API**: http://localhost:8000
- **TikTok Insights Dashboard**: http://localhost:8080

## 📋 Available Services

### Core Services
- **main-scraper**: Primary TikTok video scraping service
- **keyword-scoring**: AI-powered keyword extraction and scoring
- **reddit-scraper**: Reddit user profile and content analysis
- **performance-predictor**: ML-based performance prediction API
- **tiktok-insights**: Analytics dashboard with visualizations
- **video-analysis**: Video transcription and virality analysis

### Infrastructure Services
- **selenium-hub**: Browser automation coordination
- **chrome-node**: Chrome browser instances for Selenium
- **firefox-node**: Firefox browser instances for Selenium

## 🎛️ Service Management

### Start Individual Services
```bash
# Main scraper only
./docker-scripts/start-services.sh scraper

# Keyword scoring service
./docker-scripts/start-services.sh keyword

# Performance predictor API
./docker-scripts/start-services.sh predictor

# Insights dashboard
./docker-scripts/start-services.sh insights

# Browser automation stack
./docker-scripts/start-services.sh selenium
```

### Monitor and Debug
```bash
# View all service logs
./docker-scripts/start-services.sh logs

# View specific service logs
./docker-scripts/start-services.sh logs main-scraper

# Check service status
./docker-scripts/start-services.sh status

# Interactive shell in container
docker exec -it tiktok-main-scraper /bin/bash
```

### Stop and Cleanup
```bash
# Stop all services
./docker-scripts/start-services.sh stop

# Restart all services
./docker-scripts/start-services.sh restart

# Clean up containers and images
./docker-scripts/start-services.sh clean
```

## 📁 Volume Mounts

Data persistence is handled through volume mounts:

```yaml
Host Directory          → Container Path
./data                  → /app/data
./downloads             → /app/downloads
./models                → /app/models
./outputs               → /app/outputs
./backups               → /app/backups
./logs                  → /app/logs
./master2.json          → /app/master2.json
./urls.txt              → /app/urls.txt
```

## ⚙️ Configuration

### Environment Variables
Configure services via `.env.docker`:
- Browser settings
- API endpoints
- Worker counts
- Model configurations

### Custom Configuration
1. Copy `.env.docker` to `.env` and modify
2. Update `docker-compose.override.yml` for development settings
3. Modify service-specific environment variables

## 🔧 Advanced Usage

### Custom Commands
```bash
# Run scraper with custom parameters
docker-compose run --rm main-scraper python main.py --workers 5

# Run keyword scoring on specific file
docker-compose run --rm keyword-scoring python keyword_scorer.py /app/data/custom.json

# Execute performance prediction
docker-compose run --rm performance-predictor python predict_performance.py "content here"

# Run video analysis on specific directory
docker-compose run --rm video-analysis python analyze_ubuntu_videos.py
```

### Development Mode
```bash
# Start with development overrides (code mounting)
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# This enables live code editing without rebuilds
```

### Production Deployment
```bash
# Production build with optimizations
docker-compose -f docker-compose.yml build --no-cache

# Start production stack
docker-compose -f docker-compose.yml up -d
```

## 🧠 ML Models and Dependencies

The container includes pre-configured:
- **Whisper**: Audio transcription (base model)
- **NLTK**: Natural language processing data
- **spaCy**: English language model (en_core_web_sm)
- **scikit-learn**: Machine learning models
- **Browser drivers**: Chrome, Firefox via Selenium

Models are automatically downloaded on first run and cached in the `models/` volume.

## 🔍 Browser Automation

### Selenium Grid Architecture
- **Hub**: Coordinates browser sessions
- **Chrome Node**: Provides Chrome browser instances
- **Firefox Node**: Provides Firefox browser instances

### Browser Configuration
- Headless mode enabled by default
- Optimized for container environments
- Shared memory configured (2GB per node)
- Multiple concurrent sessions supported

## 📊 Monitoring and Health Checks

### Service Health
```bash
# Check all container health
docker-compose ps

# View resource usage
docker stats

# Check logs for errors
docker-compose logs | grep ERROR
```

### Performance Monitoring
- CPU and memory usage via `docker stats`
- Application logs in `/app/logs/`
- Selenium Grid console at http://localhost:4444

## 🚨 Troubleshooting

### Common Issues

#### Out of Memory
```bash
# Increase Docker memory limit to 8GB+
# Or reduce worker count in services
```

#### Browser Automation Fails
```bash
# Check Selenium Hub status
curl http://localhost:4444/wd/hub/status

# Restart browser nodes
docker-compose restart chrome-node firefox-node
```

#### Models Not Loading
```bash
# Manually download models
docker-compose run --rm main-scraper python -c "
import faster_whisper
model = faster_whisper.WhisperModel('base', device='cpu')
"
```

#### Permission Issues
```bash
# Fix volume permissions
sudo chmod -R 755 data downloads models outputs backups logs
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debug output
docker-compose up --remove-orphans
```

## 🔐 Security Considerations

- No sensitive data in containers (use volume mounts)
- Browser automation isolated in separate containers
- API services bound to localhost by default
- Regular security updates via base image updates

## 📈 Performance Optimization

### Resource Allocation
- **Main Scraper**: 2-4 CPU cores, 4-6GB RAM
- **ML Services**: 2-3 CPU cores, 3-4GB RAM
- **Browser Nodes**: 1-2 CPU cores, 2GB RAM each

### Scaling
```bash
# Scale browser nodes
docker-compose up -d --scale chrome-node=3

# Scale worker processes
docker-compose run --rm main-scraper python main.py --workers 6
```

## 🔄 Backup and Recovery

### Data Backup
```bash
# Backup all data volumes
tar -czf tiktok-backup-$(date +%Y%m%d).tar.gz data downloads models outputs backups

# Backup specific data
docker run --rm -v tiktok_scraper_data:/data -v $(pwd):/backup alpine tar czf /backup/data-backup.tar.gz -C /data .
```

### Container Recovery
```bash
# Rebuild from scratch
./docker-scripts/start-services.sh clean
./docker-scripts/start-services.sh build
./docker-scripts/start-services.sh all
```

## 📚 Additional Resources

- [Main README](README.md) - Project overview and features
- [Usage Guide](README_USAGE.md) - Detailed usage instructions
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Selenium Grid Documentation](https://selenium-python.readthedocs.io/)

---

**🎯 Pro Tip**: Use `./docker-scripts/start-services.sh help` for quick command reference!