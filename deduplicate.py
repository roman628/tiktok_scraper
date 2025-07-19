#!/usr/bin/env python3
"""
URL Deduplicator Script

This script takes one or more text files containing URLs (one per line) as input,
combines them, removes duplicates (both within and between files), and outputs 
the unique URLs to a specified output file.

Usage:
    python deduplicate.py file1.txt [file2.txt ...] -o output.txt

Example:
    python deduplicate.py file1.txt file2.txt file3.txt -o deduped.txt
"""

import sys
import os
import argparse
from typing import Set, List


def read_urls_from_file(filepath: str) -> tuple[Set[str], int]:
    """
    Read URLs from a text file and return them as a set and total line count.
    
    Args:
        filepath: Path to the input file
        
    Returns:
        Tuple of (unique URLs from the file, total lines read)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error reading the file
    """
    urls = set()
    total_lines = 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                # Strip whitespace and skip empty lines
                url = line.strip()
                if url:
                    urls.add(url)
                    total_lines += 1
                    
        print(f"✅ Read {total_lines} lines, {len(urls)} unique URLs from {filepath}")
        return urls, total_lines
        
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


def deduplicate_url_files(input_files: List[str], output_file: str) -> None:
    """
    Combine multiple URL files, remove duplicates (both within and between files), 
    and save to output file.
    
    Args:
        input_files: List of paths to input files
        output_file: Path to output file
    """
    print(f"🔄 Starting URL deduplication process...")
    print(f"📂 Input files ({len(input_files)}):")
    for i, file in enumerate(input_files, 1):
        print(f"   {i}. {file}")
    print(f"📝 Output file: {output_file}")
    print("-" * 50)
    
    # Read URLs from all files and track statistics
    all_urls = set()
    total_lines_all_files = 0
    file_stats = []
    
    for file_path in input_files:
        urls, total_lines = read_urls_from_file(file_path)
        file_stats.append((file_path, total_lines, len(urls)))
        all_urls.update(urls)
        total_lines_all_files += total_lines
    
    # Calculate statistics
    duplicates_removed = total_lines_all_files - len(all_urls)
    
    # Sort URLs for consistent output
    sorted_urls = sorted(list(all_urls))
    
    # Write to output file
    write_urls_to_file(sorted_urls, output_file)
    
    # Print summary statistics
    print("-" * 50)
    print("📊 DEDUPLICATION SUMMARY:")
    for file_path, total_lines, unique_in_file in file_stats:
        print(f"   {os.path.basename(file_path)}: {total_lines} lines, {unique_in_file} unique")
    print(f"   Total input lines: {total_lines_all_files}")
    print(f"   Duplicates found: {duplicates_removed}")
    print(f"   Unique URLs: {len(all_urls)}")
    print(f"   Output file: {output_file}")
    print("✨ Deduplication complete!")


def main():
    """Main function to handle command line arguments and execute deduplication."""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Deduplicate URLs from multiple text files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deduplicate.py file1.txt -o output.txt
  python deduplicate.py file1.txt file2.txt file3.txt -o deduped.txt
  python deduplicate.py urls/*.txt -o combined_unique.txt
        """)
    
    parser.add_argument('input_files', nargs='+', 
                       help='One or more input text files containing URLs')
    parser.add_argument('-o', '--output', required=True,
                       help='Output file for deduplicated URLs')
    
    args = parser.parse_args()
    
    # Validate input files exist
    for filepath in args.input_files:
        if not os.path.isfile(filepath):
            print(f"❌ Error: Input file '{filepath}' does not exist.")
            sys.exit(1)
    
    # Check if output file already exists
    if os.path.exists(args.output):
        response = input(f"⚠️  Output file '{args.output}' already exists. Overwrite? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Operation cancelled.")
            sys.exit(1)
    
    try:
        deduplicate_url_files(args.input_files, args.output)
        
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