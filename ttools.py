#!/usr/bin/env python3

import os
import subprocess
import sys
import importlib.util
import re

def get_script_info(script_path):
    """Returns description for known scripts."""
    script_descriptions = {
        # Main scripts
        "main.py": "🚀 Main TikTok scraper with clean architecture (RECOMMENDED)",
        "robust_master_downloader.py": "⚠️  Legacy complex downloader (deprecated)",
        
        # Analysis scripts
        "comment_extractor.py": "Extract comments from TikTok videos and update master.json",
        "count.py": "Count posts and comments from master JSON files",
        "count_master.py": "Analyze entries in master2.json with error recovery",
        
        # Cleanup scripts
        "sanitize_json.py": "Extract videos with transcriptions > 40 chars",
        "fix_json.py": "Fix corrupted JSON files by extracting valid objects",
        "remove_duplicates.py": "Remove duplicate URLs keeping most complete data",
        "clean_no_transcription.py": "Remove entries without transcriptions",
        "deduplicate.py": "Remove duplicate URLs from text files",
        
        # Collection scripts
        "browser_harvester.py": "Harvest URLs from existing Firefox browser",
        "tiktok_url_collector.py": "Collect URLs with stealth browser mode",
        "url_harvester.py": "Harvest URLs from trending/hashtags/users/searches",
        "update_comments_v2.py": "Update master2.json with video comments",
        "master_download_and_comment.py": "Download videos and extract comments",
        "tiktok_scraper.py": "Multi-process downloader with resume capability",
        "tiktok_downloader.py": "Simple video downloader using yt-dlp",
        
        # Utils scripts
        "connect_existing_firefox.py": "Connect to Firefox for remote debugging",
        "memory_efficient_append.py": "Stream append JSON without loading all data",
        "process_single_video.py": "Extract comments from a single video"
    }
    
    script_name = os.path.basename(script_path)
    return script_descriptions.get(script_name, "No description available.")

def get_script_arguments(script_path):
    """Extract usage/argument information from script by running with --help or analyzing source."""
    script_name = os.path.basename(script_path)
    
    # Try to get help output first
    try:
        result = subprocess.run([sys.executable, script_path, '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            return parse_help_output(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    
    # Try -h if --help failed
    try:
        result = subprocess.run([sys.executable, script_path, '-h'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            return parse_help_output(result.stdout)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    
    # Try to parse usage from source code
    return parse_usage_from_source(script_path)

def parse_help_output(help_text):
    """Parse argparse help output to extract options."""
    options = []
    
    # Look for options section
    lines = help_text.split('\n')
    in_options = False
    current_option = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Start of options section
        if line.lower().startswith('optional arguments:') or line.lower().startswith('options:'):
            in_options = True
            continue
        
        # End of options section (another section starts)    
        if in_options and line.endswith(':') and not line.startswith('-'):
            break
            
        if in_options:
            # Option line starts with - or --
            if line.startswith('-'):
                # Extract option and description
                parts = line.split(None, 1)
                if len(parts) >= 1:
                    option_flags = parts[0]
                    description = parts[1] if len(parts) > 1 else ""
                    
                    # Clean up option flags
                    flags = [f.strip(',') for f in option_flags.split() if f.startswith('-')]
                    
                    if flags:
                        options.append({
                            'flags': flags,
                            'description': description,
                            'takes_value': any(' ' in flag or '=' in flag for flag in flags) or 
                                         any(flag.endswith('=') for flag in flags) or
                                         ('TYPE' in description.upper() or 'FILE' in description.upper() or 
                                          'PATH' in description.upper() or 'NUMBER' in description.upper() or
                                          'VALUE' in description.upper())
                        })
    
    return options

def parse_usage_from_source(script_path):
    """Parse usage information from script source code."""
    options = []
    
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for usage patterns in docstrings or print statements
        usage_patterns = [
            r'Usage:\s*\n(.*?)(?:\n\n|\nOptions:|\nExamples:|\Z)',
            r'usage:\s*\n(.*?)(?:\n\n|\noptions:|\nexamples:|\Z)',
            r'print\s*\(\s*[\'"]Usage:(.*?)[\'"]'
        ]
        
        for pattern in usage_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                usage_text = match.group(1).strip()
                if usage_text:
                    # Simple parsing - look for --flags
                    flags = re.findall(r'--[\w-]+', usage_text)
                    for flag in flags:
                        options.append({
                            'flags': [flag],
                            'description': f"Option {flag}",
                            'takes_value': '[' in usage_text or '=' in usage_text
                        })
                    break
    except Exception:
        pass
    
    return options

def show_argument_menu(script_path):
    """Show argument selection menu for scripts that accept parameters."""
    script_name = os.path.basename(script_path)
    
    # First try to get usage/help information
    usage_output = ""
    
    # Try running without arguments first (many scripts show usage)
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, timeout=10)
        if result.stdout and ("Usage:" in result.stdout or "usage:" in result.stdout):
            usage_output = result.stdout
    except:
        pass
    
    # If no usage from no-args, try --help
    if not usage_output:
        try:
            result = subprocess.run([sys.executable, script_path, '--help'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                usage_output = result.stdout
        except:
            pass
    
    # If no usage yet, try -h
    if not usage_output:
        try:
            result = subprocess.run([sys.executable, script_path, '-h'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout:
                usage_output = result.stdout
        except:
            pass
    
    # If we have usage info, show numbered options directly
    if usage_output:
        print(f"\n📋 Available arguments for {script_name}:")
        print("="*60)
        print(usage_output)
        print("="*60)
        
        # Parse and number the options
        options = []
        
        # Extract common flags from usage output
        flag_patterns = [
            (r'--dry-run', '--dry-run', 'Show what would be removed without actually removing'),
            (r'--force', '--force', 'Skip confirmation prompt'),
            (r'--help', '--help', 'Show help message'),
            (r'-h\b', '-h', 'Show help message'),
            (r'--verbose', '--verbose', 'Enable verbose output'),
            (r'-v\b', '-v', 'Enable verbose output'),
            (r'--output', '--output', 'Specify output file/directory'),
            (r'-o\b', '-o', 'Specify output file/directory'),
        ]
        
        for pattern, flag, description in flag_patterns:
            if re.search(pattern, usage_output):
                # Check if we already added this flag (avoid duplicates like -h and --help)
                if not any(existing_flag == flag for existing_flag, _ in options):
                    options.append((flag, description))
        
        # Add positional arguments if mentioned
        if '[input_file]' in usage_output or 'input_file' in usage_output:
            options.append(('<input_file>', 'Input file path'))
        if '[output_file]' in usage_output or 'output_file' in usage_output:
            options.append(('<output_file>', 'Output file path'))
        
        if options:
            print("Select arguments by number:")
            for i, (flag, desc) in enumerate(options, 1):
                print(f"{i}. {flag}: {desc}")
            print(f"{len(options) + 1}. <manual>: Type arguments manually")
            print(f"{len(options) + 2}. <none>: Run without arguments")
            print()
            
            choice_input = input("Enter your choice (numbers and values, e.g., '1 2 file.json' or 'manual'): ").strip()
            
            if choice_input.lower() in ['manual', str(len(options) + 1)]:
                args_input = input("Enter arguments manually: ").strip()
                return args_input.split() if args_input else []
            
            elif choice_input.lower() in ['none', str(len(options) + 2), '']:
                return []
            
            else:
                # Parse numbered selections
                selected_args = []
                parts = choice_input.split()
                
                for part in parts:
                    try:
                        option_num = int(part)
                        if 1 <= option_num <= len(options):
                            flag, _ = options[option_num - 1]
                            if not flag.startswith('<'):  # Skip placeholder options
                                selected_args.append(flag)
                        else:
                            # Not a valid option number, treat as file/value
                            selected_args.append(part)
                    except ValueError:
                        # Not a number, treat as file/value
                        selected_args.append(part)
                
                return selected_args
        else:
            # No options detected, ask for manual input
            print("No specific options detected.")
            args_input = input("Enter arguments manually (or press Enter to run without arguments): ").strip()
            return args_input.split() if args_input else []
    
    else:
        # No usage info found, run without arguments
        return []

def find_scripts(directory="scripts"):
    """Finds all Python scripts in the given directory and its subdirectories, ignoring __init__.py."""
    scripts = []
    
    # Add main scripts in root directory
    root_scripts = ["main.py", "robust_master_downloader.py"]
    for script in root_scripts:
        if os.path.exists(script):
            scripts.append(script)
    
    # Add scripts from scripts directory
    if os.path.exists(directory):
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    scripts.append(os.path.join(root, file))
    
    return scripts

def main():
    """Main function to display and run scripts."""
    scripts = find_scripts()
    if not scripts:
        print("No scripts found.")
        return

    print("🛠️  TikTok Scraper Tools")
    print("="*50)
    print("Available scripts:")
    
    for i, script in enumerate(scripts):
        script_name = os.path.basename(script).replace('.py', '')
        description = get_script_info(script)
        
        # Highlight recommended script
        if script_name == "main":
            print(f"{i + 1}. {script_name}: {description} ⭐")
        else:
            print(f"{i + 1}. {script_name}: {description}")
    
    print("="*50)
    print("💡 Tip: Use 'main.py' (option 1) for the best experience with clean architecture!")
    print("⚠️  The legacy 'robust_master_downloader.py' is deprecated.")
    print()

    try:
        choice = int(input("Enter the number of the script to run: "))
        if 1 <= choice <= len(scripts):
            script_path = scripts[choice - 1]
            script_name = os.path.basename(script_path)
            
            # Special handling for main.py
            if script_name == "main.py":
                print("🚀 Running the new clean architecture TikTok scraper...")
                print("   This uses the unified, simplified codebase.")
            elif script_name == "robust_master_downloader.py":
                print("⚠️  Running legacy downloader...")
                print("   Consider using main.py instead for better performance and maintainability.")
            else:
                print(f"Running {script_path}...")
            
            # Check if script accepts arguments and show menu
            script_args = []
            if script_name != "main.py":  # main.py has its own interactive system
                script_args = show_argument_menu(script_path)
            
            # Run the script with selected arguments
            cmd = [sys.executable, script_path] + script_args
            print(f"\n🚀 Executing: {' '.join(cmd)}")
            print("="*60)
            subprocess.run(cmd)
        else:
            print("Invalid choice.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")

if __name__ == "__main__":
    main()
