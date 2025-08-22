#!/usr/bin/env python3
"""Test script to verify collector.py is working after fixes"""

import subprocess
import sys
import time
import os

def test_collector():
    """Test collector with a simple URL"""
    print("Testing collector.py with enhanced worker process...")
    
    # Create test URLs file
    test_urls = [
        "https://www.tiktok.com/@zachking/video/6768504823336815877"
    ]
    
    with open("test_urls.txt", "w") as f:
        for url in test_urls:
            f.write(url + "\n")
    
    # Run collector
    cmd = [sys.executable, "collector.py", "--from-file", "test_urls.txt", "--workers", "1"]
    print(f"Running: {' '.join(cmd)}")
    
    try:
        # Run with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in iter(process.stdout.readline, ''):
            if line:
                print(line.rstrip())
        
        # Wait for completion
        return_code = process.wait()
        
        if return_code == 0:
            print("\n✅ Collector completed successfully!")
        else:
            print(f"\n❌ Collector failed with return code: {return_code}")
            
        return return_code == 0
        
    except Exception as e:
        print(f"\n❌ Error running collector: {e}")
        return False
    finally:
        # Cleanup
        if os.path.exists("test_urls.txt"):
            os.remove("test_urls.txt")

def check_worker_status_table():
    """Check if worker_status table exists"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="tiktok_scraper",
            user="postgres"
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'worker_status'
            """)
            result = cur.fetchone()
            if result:
                print("✅ worker_status table exists")
                # Check contents
                cur.execute("SELECT COUNT(*) FROM worker_status")
                count = cur.fetchone()[0]
                print(f"   Current worker entries: {count}")
            else:
                print("⚠️  worker_status table does not exist (will be created on first run)")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

if __name__ == "__main__":
    print("=== TikTok Collector Fix Test ===\n")
    
    # Check database
    print("1. Checking database setup...")
    check_worker_status_table()
    
    print("\n2. Testing collector...")
    success = test_collector()
    
    # Check logs
    print("\n3. Checking logs directory...")
    if os.path.exists("logs"):
        log_files = [f for f in os.listdir("logs") if f.startswith("collector_")]
        if log_files:
            print(f"✅ Found {len(log_files)} log file(s)")
            latest = max(log_files, key=lambda f: os.path.getmtime(os.path.join("logs", f)))
            print(f"   Latest: {latest}")
        else:
            print("⚠️  No collector log files found")
    else:
        print("⚠️  Logs directory not found")
    
    print("\n=== Test Complete ===")
    sys.exit(0 if success else 1)