#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Python path:", sys.path[:3])  # First 3 paths

# Try to import
try:
    import comment_extractor
    print("✅ Successfully imported comment_extractor")
    print("   File location:", comment_extractor.__file__)
except ImportError as e:
    print("❌ Failed to import comment_extractor:", e)

# Check if file exists
if os.path.exists("comment_extractor.py"):
    print("✅ comment_extractor.py exists in current directory")
else:
    print("❌ comment_extractor.py NOT found in current directory")

# List files in current directory
print("\nFiles in current directory:")
for f in os.listdir("."):
    if f.endswith(".py"):
        print(f"  - {f}")