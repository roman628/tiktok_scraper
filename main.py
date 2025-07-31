#!/usr/bin/env python3
"""
Main Menu for Master TikTok Downloader
Simple menu interface to execute the master downloader
"""

import sys
import subprocess

def main():
    """Simple menu with one option"""
    print("🚀 Master TikTok Downloader")
    print("=" * 50)
    print("1. Run Master Downloader")
    print("2. Exit")
    print("=" * 50)
    
    choice = input("Select option (1-2): ").strip()
    
    if choice == "1":
        try:
            subprocess.run([sys.executable, "master_downloader.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error: {e.returncode}")
        except KeyboardInterrupt:
            print("\n🛑 Interrupted")
    elif choice == "2":
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()