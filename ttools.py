#!/usr/bin/env python3

import os
import subprocess
import sys
import importlib.util

def get_script_info(script_path):
    """Extracts the docstring from a Python script."""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
            docstring = ast.get_docstring(tree)
            return docstring.strip().split('\n')[0] if docstring else "No description available."
    except Exception:
        return "No description available."

def find_scripts(directory="scripts"):
    """Finds all Python scripts in the given directory and its subdirectories, ignoring __init__.py."""
    scripts = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                scripts.append(os.path.join(root, file))
    return scripts

def main():
    """Main function to display and run scripts."""
    import ast
    scripts = find_scripts()
    if not scripts:
        print("No scripts found.")
        return

    print("Available scripts:")
    for i, script in enumerate(scripts):
        script_name = os.path.basename(script).replace('.py', '')
        description = get_script_info(script)
        print(f"{i + 1}. {script_name}: {description}")

    try:
        choice = int(input("Enter the number of the script to run: "))
        if 1 <= choice <= len(scripts):
            script_path = scripts[choice - 1]
            print(f"Running {script_path}...")
            subprocess.run([sys.executable, script_path])
        else:
            print("Invalid choice.")
    except ValueError:
        print("Invalid input. Please enter a number.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")

if __name__ == "__main__":
    main()
