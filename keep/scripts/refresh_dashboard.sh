#!/bin/bash

# Script to refresh the TikTok dashboard with hot reloading

echo "🚀 TikTok Intelligence Platform - Dashboard Manager"
echo "=================================================="

case "$1" in
  start)
    echo "Starting dashboard with hot reloading..."
    docker-compose up -d frontend
    echo "✅ Dashboard running at http://localhost:3000"
    echo "🔄 Hot reloading enabled - changes will auto-refresh!"
    ;;
  
  stop)
    echo "Stopping dashboard..."
    docker-compose stop frontend
    echo "✅ Dashboard stopped"
    ;;
  
  restart)
    echo "Restarting dashboard..."
    docker-compose restart frontend
    echo "✅ Dashboard restarted"
    ;;
  
  rebuild)
    echo "Rebuilding dashboard (for package changes)..."
    docker-compose down frontend
    docker-compose up -d --build frontend
    echo "✅ Dashboard rebuilt and running"
    ;;
  
  logs)
    echo "Showing dashboard logs..."
    docker-compose logs -f frontend
    ;;
  
  status)
    echo "Dashboard status:"
    docker ps | grep tiktok-frontend || echo "❌ Dashboard not running"
    ;;
  
  *)
    echo "Usage: $0 {start|stop|restart|rebuild|logs|status}"
    echo ""
    echo "Commands:"
    echo "  start   - Start the dashboard with hot reloading"
    echo "  stop    - Stop the dashboard"
    echo "  restart - Restart the dashboard"
    echo "  rebuild - Rebuild container (needed after package.json changes)"
    echo "  logs    - Show dashboard logs"
    echo "  status  - Check if dashboard is running"
    exit 1
    ;;
esac