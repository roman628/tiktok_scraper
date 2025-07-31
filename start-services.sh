#!/bin/bash

# TikTok Scraper Docker Services Management Script

set -e

echo "🐳 TikTok Scraper Docker Services Manager"
echo "========================================"

# Create necessary directories
mkdir -p data downloads models outputs backups logs

# Function to start specific service
start_service() {
    local service=$1
    echo "🚀 Starting $service..."
    docker-compose up -d $service
    echo "✅ $service started"
}

# Function to show service status
show_status() {
    echo "📊 Service Status:"
    docker-compose ps
}

# Function to show logs
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        echo "📝 All service logs:"
        docker-compose logs --tail=50 -f
    else
        echo "📝 Logs for $service:"
        docker-compose logs --tail=50 -f $service
    fi
}

# Function to stop all services
stop_services() {
    echo "🛑 Stopping all services..."
    docker-compose down
    echo "✅ All services stopped"
}

# Main menu
case "${1:-help}" in
    "all")
        echo "🚀 Starting all services..."
        docker-compose up -d
        show_status
        ;;
    "scraper")
        start_service "main-scraper"
        ;;
    "keyword")
        start_service "keyword-scoring"
        ;;
    "reddit")
        start_service "reddit-scraper"
        ;;
    "predictor")
        start_service "performance-predictor"
        echo "🌐 Predictor API available at: http://localhost:8000"
        ;;
    "insights")
        start_service "tiktok-insights"
        echo "📊 Insights dashboard available at: http://localhost:8080"
        ;;
    "video")
        start_service "video-analysis"
        ;;
    "selenium")
        start_service "selenium-hub"
        start_service "chrome-node"
        start_service "firefox-node"
        echo "🌐 Selenium Hub available at: http://localhost:4444"
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs $2
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        docker-compose up -d
        show_status
        ;;
    "build")
        echo "🔨 Building containers..."
        docker-compose build --parallel
        echo "✅ Build complete"
        ;;
    "clean")
        echo "🧹 Cleaning up containers and images..."
        docker-compose down --rmi all --volumes --remove-orphans
        echo "✅ Cleanup complete"
        ;;
    "help"|*)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  all       - Start all services"
        echo "  scraper   - Start main scraper service"
        echo "  keyword   - Start keyword scoring service"
        echo "  reddit    - Start Reddit scraper service"
        echo "  predictor - Start performance predictor API"
        echo "  insights  - Start insights dashboard"
        echo "  video     - Start video analysis service"
        echo "  selenium  - Start Selenium hub and nodes"
        echo "  status    - Show service status"
        echo "  logs [service] - Show logs (all or specific service)"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  build     - Build all containers"
        echo "  clean     - Clean up containers and images"
        echo "  help      - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 all                    # Start everything"
        echo "  $0 scraper                # Start just the scraper"
        echo "  $0 logs main-scraper      # Show scraper logs"
        echo "  $0 status                 # Check what's running"
        ;;
esac