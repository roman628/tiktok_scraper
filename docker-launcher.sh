#!/bin/bash

# TikTok Scraper Docker Launcher
# Simple script to manage Docker services with graceful startup and shutdown

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.yml"
SERVICES_SCRIPT="./docker-scripts/start-services.sh"

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Check if required files exist
check_files() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "docker-compose.yml not found in current directory"
        exit 1
    fi
    
    if [[ ! -f "$SERVICES_SCRIPT" ]]; then
        print_error "Services script not found: $SERVICES_SCRIPT"
        exit 1
    fi
    
    if [[ ! -x "$SERVICES_SCRIPT" ]]; then
        print_warning "Making services script executable..."
        chmod +x "$SERVICES_SCRIPT"
    fi
}

# Show usage information
show_usage() {
    echo "TikTok Scraper Docker Launcher"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start       Build and start all Docker services"
    echo "  stop        Gracefully stop all services"
    echo "  restart     Restart all services"
    echo "  status      Show status of all services"
    echo "  logs        Show logs from all services"
    echo "  clean       Stop services and clean up containers/images"
    echo "  build       Build/rebuild Docker images"
    echo "  help        Show this help message"
    echo ""
    echo "Service URLs (when running):"
    echo "  - Selenium Hub: http://localhost:4444"
    echo "  - Performance Predictor API: http://localhost:8000"
    echo "  - TikTok Insights Dashboard: http://localhost:8080"
}

# Start services
start_services() {
    print_status "Starting TikTok Scraper Docker services..."
    
    # Build if needed
    print_status "Building Docker images..."
    docker-compose build
    
    # Start services
    print_status "Starting all services..."
    $SERVICES_SCRIPT all
    
    # Wait a moment for services to initialize
    sleep 5
    
    # Check status
    print_status "Checking service status..."
    $SERVICES_SCRIPT status
    
    print_success "All services started successfully!"
    echo ""
    echo "Access points:"
    echo "  - Selenium Hub: http://localhost:4444"
    echo "  - Performance Predictor API: http://localhost:8000"
    echo "  - TikTok Insights Dashboard: http://localhost:8080"
}

# Stop services gracefully
stop_services() {
    print_status "Stopping TikTok Scraper Docker services gracefully..."
    
    # Use the services script to stop
    $SERVICES_SCRIPT stop
    
    # Wait for graceful shutdown
    print_status "Waiting for services to stop gracefully..."
    sleep 3
    
    # Force stop any remaining containers
    if docker-compose ps -q | grep -q .; then
        print_warning "Force stopping remaining containers..."
        docker-compose down
    fi
    
    print_success "All services stopped successfully!"
}

# Restart services
restart_services() {
    print_status "Restarting TikTok Scraper Docker services..."
    stop_services
    sleep 2
    start_services
}

# Show service status
show_status() {
    print_status "Checking service status..."
    $SERVICES_SCRIPT status
    
    echo ""
    print_status "Docker container status:"
    docker-compose ps
}

# Show logs
show_logs() {
    print_status "Showing service logs..."
    $SERVICES_SCRIPT logs
}

# Clean up everything
clean_services() {
    print_warning "This will stop all services and remove containers/images."
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cleaning up Docker services..."
        $SERVICES_SCRIPT clean
        print_success "Cleanup completed!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Build images
build_images() {
    print_status "Building Docker images..."
    docker-compose build --no-cache
    print_success "Images built successfully!"
}

# Trap Ctrl+C for graceful shutdown
trap 'print_warning "Received interrupt signal. Stopping services..."; stop_services; exit 0' INT

# Main script logic
main() {
    check_docker
    check_files
    
    case "${1:-}" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        clean)
            clean_services
            ;;
        build)
            build_images
            ;;
        help|--help|-h)
            show_usage
            ;;
        "")
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"