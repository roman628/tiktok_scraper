#!/bin/bash

# TikTok Intelligence Platform Deployment Script
# Automates the complete deployment process

set -e

echo "🚀 TikTok Intelligence Platform Deployment"
echo "=========================================="

# Configuration
PROJECT_NAME="tiktok-platform"
COMPOSE_FILE="docker/docker-compose.yml"
ENV_FILE=".env"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        log_info "Creating .env file..."
        cat > "$ENV_FILE" << EOF
# TikTok Intelligence Platform Configuration

# TikTok API Configuration (Required for comment extraction)
TIKTOK_MS_TOKEN=

# Database Configuration
POSTGRES_DB=tiktok_platform
POSTGRES_USER=tiktok_user
POSTGRES_PASSWORD=secure_password_$(date +%s)

# API Configuration
API_BASE_URL=http://localhost:8080
ENVIRONMENT=production

# Logging
LOG_LEVEL=INFO

# Pipeline Configuration
MAX_CONCURRENT_VIDEOS=10
MAX_COMMENTS_PER_VIDEO=20
EOF
        log_warning "Created .env file. Please add your TIKTOK_MS_TOKEN for comment extraction."
    else
        log_info ".env file already exists"
    fi
    
    # Create data directories
    mkdir -p data logs
    
    log_success "Environment setup completed"
}

# Build and deploy
deploy() {
    log_info "Building and deploying platform..."
    
    # Stop existing containers
    log_info "Stopping existing containers..."
    docker-compose -f "$COMPOSE_FILE" down || true
    
    # Remove old volumes for fresh deployment
    log_info "Removing existing volumes for fresh deployment..."
    docker-compose -f "$COMPOSE_FILE" down -v || true
    
    # Build images
    log_info "Building Docker images..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    # Start services
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Platform deployed successfully"
}

# Wait for services
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for API to be healthy
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8080/api/health &> /dev/null; then
            log_success "API is ready"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "API failed to start within timeout"
            return 1
        fi
        
        log_info "Waiting for API... (attempt $attempt/$max_attempts)"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    # Check database connectivity
    if docker-compose -f "$COMPOSE_FILE" exec -T tiktok-platform curl -f http://localhost:8080/api/health/database &> /dev/null; then
        log_success "Database is ready"
    else
        log_warning "Database health check failed"
    fi
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check service status
    local services_status=$(docker-compose -f "$COMPOSE_FILE" ps --services --filter "status=running" | wc -l)
    local total_services=$(docker-compose -f "$COMPOSE_FILE" config --services | wc -l)
    
    if [ "$services_status" -eq "$total_services" ]; then
        log_success "All services are running"
    else
        log_warning "Some services may not be running properly"
    fi
    
    # Test API endpoints
    local endpoints=(
        "http://localhost:8080/"
        "http://localhost:8080/api/health"
        "http://localhost:3000"
    )
    
    for endpoint in "${endpoints[@]}"; do
        if curl -f "$endpoint" &> /dev/null; then
            log_success "✓ $endpoint is accessible"
        else
            log_warning "✗ $endpoint is not accessible"
        fi
    done
}

# Show deployment info
show_deployment_info() {
    echo
    echo "🎉 Deployment Summary"
    echo "===================="
    echo "📱 API Server:      http://localhost:8080"
    echo "📊 Dashboard:       http://localhost:3000"
    echo "🗄️  Database:        localhost:5432"
    echo "📖 API Docs:        http://localhost:8080/api/docs"
    echo
    echo "🔧 Management Commands:"
    echo "  View logs:        docker-compose -f $COMPOSE_FILE logs -f"
    echo "  Stop platform:    docker-compose -f $COMPOSE_FILE down"
    echo "  Restart:          docker-compose -f $COMPOSE_FILE restart"
    echo "  Update:           ./scripts/deploy.sh"
    echo
    echo "🦊 Firefox Extension:"
    echo "  Install from:     ./extensions/firefox/"
    echo "  Auto-connects to: http://localhost:8080/api"
    echo
    
    if [ ! -s "$ENV_FILE" ] || ! grep -q "TIKTOK_MS_TOKEN=." "$ENV_FILE"; then
        echo "⚠️  IMPORTANT: Add your TIKTOK_MS_TOKEN to .env for comment extraction"
    fi
    
    echo
    log_success "TikTok Intelligence Platform is ready! 🚀"
}

# Error handling
cleanup_on_error() {
    log_error "Deployment failed. Cleaning up..."
    docker-compose -f "$COMPOSE_FILE" down
    exit 1
}

# Set up error handling
trap cleanup_on_error ERR

# Main deployment flow
main() {
    echo "Starting deployment process..."
    
    check_prerequisites
    setup_environment
    deploy
    wait_for_services
    verify_deployment
    show_deployment_info
}

# Parse command line arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log_info "Stopping platform..."
        docker-compose -f "$COMPOSE_FILE" down
        log_success "Platform stopped"
        ;;
    "restart")
        log_info "Restarting platform..."
        docker-compose -f "$COMPOSE_FILE" restart
        log_success "Platform restarted"
        ;;
    "logs")
        docker-compose -f "$COMPOSE_FILE" logs -f
        ;;
    "status")
        docker-compose -f "$COMPOSE_FILE" ps
        ;;
    "clean")
        log_warning "This will remove all containers, volumes, and data!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose -f "$COMPOSE_FILE" down -v --rmi all
            log_success "Platform cleaned"
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|logs|status|clean}"
        echo
        echo "Commands:"
        echo "  deploy   - Deploy the platform (default)"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Show service logs"
        echo "  status   - Show service status"
        echo "  clean    - Remove everything (destructive)"
        exit 1
        ;;
esac