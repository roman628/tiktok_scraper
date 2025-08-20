#!/bin/bash

# Test Runner for robust_master_downloader.py
# This script runs the test framework with proper configuration

echo "=========================================="
echo "TikTok Downloader Test Suite"
echo "=========================================="
echo ""

# Check if test_config.toml exists
if [ ! -f "test_config.toml" ]; then
    echo "❌ Error: test_config.toml not found!"
    echo "Please create test_config.toml with your MS_TOKEN"
    exit 1
fi

# Check if MS_TOKEN is configured
if grep -q "YOUR_MS_TOKEN_HERE" test_config.toml; then
    echo "⚠️  Warning: MS_TOKEN not configured in test_config.toml"
    echo "Edit test_config.toml and replace 'YOUR_MS_TOKEN_HERE' with a valid token"
    echo "Comments extraction will be skipped during testing"
    echo ""
    read -p "Continue without MS_TOKEN? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if test URLs file exists
if [ ! -f "test_urls.txt" ]; then
    echo "❌ Error: test_urls.txt not found!"
    exit 1
fi

echo "📋 Test Configuration:"
echo "  • Config file: test_config.toml"
echo "  • URLs file: test_urls.txt"
echo "  • URLs to test: $(grep -c '^http' test_urls.txt)"
echo ""

# Run the test framework
echo "🚀 Starting tests..."
echo ""

python3 test_robust_downloader.py --config test_config.toml

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Tests completed successfully!"
    echo ""
    echo "📊 View detailed results in:"
    echo "  • test_report.json - Full test report"
    echo "  • test_run.log - Detailed execution log"
    echo "  • test_output.json - Processed video data"
else
    echo ""
    echo "❌ Tests failed!"
    echo "Check test_report.json and test_run.log for details"
fi