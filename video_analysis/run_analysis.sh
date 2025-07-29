#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Run the analysis
echo "Starting video analysis of ubuntu-results directory..."
echo "This may take some time depending on the number of videos..."
echo ""

python video_analysis/analyze_ubuntu_videos.py

echo ""
echo "Analysis complete!"
echo "Check the results in: video_analysis/reports/ubuntu_results/"