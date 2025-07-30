#!/bin/bash
# Run the improved TikTok insights dashboard

echo "🚀 Running Improved TikTok Insights Dashboard..."
echo "=============================================="

# Navigate to scripts directory
cd "$(dirname "$0")"

# Run the improved dashboard
python improved_dashboard.py

echo ""
echo "✅ Dashboard analysis complete!"
echo "📊 Check the outputs:"
echo "   - Dashboard: ../charts/improved_tiktok_dashboard.png"
echo "   - Report: ../outputs/improved_insights_report.json"