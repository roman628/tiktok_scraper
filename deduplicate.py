#!/usr/bin/env python3
"""
URL Deduplicator Script

This script takes two text files containing URLs (one per line) as input,
combines them, removes duplicates, and outputs the unique URLs to a third file.

Usage:
    python url_deduplicator.py file1.txt file2.txt output.txt

Example:
    python url_deduplicator.py tiktok_urls_1.txt tiktok_urls_2.txt combined_urls.txt
"""

import sys
import os
from typing import Set, List


def read_urls_from_file(filepath: str) -> Set[str]:
    """
    Read URLs from a text file and return them as a set (automatically deduplicates).
    
    Args:
        filepath: Path to the input file
        
    Returns:
        Set of unique URLs from the file
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    urls = set()
    
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                # Strip whitespace and skip empty lines
                url = line.strip()
                if url:
                    urls.add(url)
                    
        print(f"✅ Read {len(urls)} unique URLs from {filepath}")
        return urls
        
    except FileNotFoundError:
        print(f"❌ Error: File '{filepath}' not found.")
        raise
    except IOError as e:
        print(f"❌ Error reading file '{filepath}': {e}")
        raise


def write_urls_to_file(urls: List[str], filepath: str) -> None:
    """
    Write URLs to a text file, one per line.
    
    Args:
        urls: List of URLs to write
        filepath: Path to the output file
        
    Raises:
        IOError: If there's an error writing the file
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            for url in urls:
                file.write(f"{url}\n")
                
        print(f"✅ Successfully wrote {len(urls)} URLs to {filepath}")
        
    except IOError as e:
        print(f"❌ Error writing to file '{filepath}': {e}")
        raise


def deduplicate_url_files(file1: str, file2: str, output_file: str) -> None:
    """
    Combine two URL files, remove duplicates, and save to output file.
    
    Args:
        file1: Path to first input file
        file2: Path to second input file
        output_file: Path to output file
    """
    print(f"🔄 Starting URL deduplication process...")
    print(f"📂 Input file 1: {file1}")
    print(f"📂 Input file 2: {file2}")
    print(f"📝 Output file: {output_file}")
    print("-" * 50)
    
    # Read URLs from both files
    urls1 = read_urls_from_file(file1)
    urls2 = read_urls_from_file(file2)
    
    # Combine and get statistics
    combined_urls = urls1.union(urls2)
    total_input_urls = len(urls1) + len(urls2)
    duplicates_removed = total_input_urls - len(combined_urls)
    
    # Sort URLs for consistent output
    sorted_urls = sorted(list(combined_urls))
    
    # Write to output file
    write_urls_to_file(sorted_urls, output_file)
    
    # Print summary statistics
    print("-" * 50)
    print("📊 DEDUPLICATION SUMMARY:")
    print(f"   File 1 URLs: {len(urls1)}")
    print(f"   File 2 URLs: {len(urls2)}")
    print(f"   Total input URLs: {total_input_urls}")
    print(f"   Duplicates removed: {duplicates_removed}")
    print(f"   Unique URLs: {len(combined_urls)}")
    print(f"   Output file: {output_file}")
    print("✨ Deduplication complete!")


def main():
    """Main function to handle command line arguments and execute deduplication."""
    
    # Check command line arguments
    if len(sys.argv) != 4:
        print("❌ Error: Incorrect number of arguments.")
        print("\nUsage:")
        print("   python url_deduplicator.py <file1> <file2> <output_file>")
        print("\nExample:")
        print("   python url_deduplicator.py urls1.txt urls2.txt combined.txt")
        print("\nDescription:")
        print("   Combines two text files containing URLs (one per line),")
        print("   removes duplicates, and saves unique URLs to output file.")
        sys.exit(1)
    
    file1, file2, output_file = sys.argv[1], sys.argv[2], sys.argv[3]
    
    # Validate input files exist
    for filepath in [file1, file2]:
        if not os.path.isfile(filepath):
            print(f"❌ Error: Input file '{filepath}' does not exist.")
            sys.exit(1)
    
    # Check if output file already exists
    if os.path.exists(output_file):
        response = input(f"⚠️  Output file '{output_file}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Operation cancelled.")
            sys.exit(1)
    
    try:
        deduplicate_url_files(file1, file2, output_file)
        
    except (FileNotFoundError, IOError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()