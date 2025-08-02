#!/usr/bin/env python3
"""
Fix corrupted JSON file by extracting individual JSON objects and rebuilding
"""

import json
import re
import os
import sys
import platform
from datetime import datetime

# Handle Windows encoding issues
if platform.system() == 'Windows':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def safe_print(message):
    """Print message with fallback for encoding issues"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback: replace emojis with text equivalents
        fallback_message = (message
                          .replace('💾', '[BACKUP]')
                          .replace('🔧', '[FIXING]')
                          .replace('✅', '[SUCCESS]')
                          .replace('❌', '[ERROR]')
                          .replace('📊', '[INFO]')
                          .replace('🔗', '[URL]')
                          .replace('⚠️', '[WARNING]'))
        print(fallback_message)

def extract_json_objects(content):
    """Extract individual JSON objects from potentially corrupted content"""
    objects = []
    
    # Split content by lines
    lines = content.split('\n')
    
    current_object = []
    brace_count = 0
    in_object = False
    
    for line in lines:
        # Check if line starts a new JSON object
        if line.strip().startswith('{') and brace_count == 0:
            in_object = True
            current_object = [line]
            brace_count = line.count('{') - line.count('}')
        elif in_object:
            current_object.append(line)
            brace_count += line.count('{') - line.count('}')
            
            # Check if object is complete
            if brace_count == 0:
                # Try to parse the object
                try:
                    obj_text = '\n'.join(current_object)
                    obj = json.loads(obj_text)
                    objects.append(obj)
                    in_object = False
                    current_object = []
                except json.JSONDecodeError:
                    # If parsing fails, try to fix common issues
                    try:
                        # Remove trailing comma if exists
                        obj_text = obj_text.rstrip()
                        if obj_text.endswith(','):
                            obj_text = obj_text[:-1]
                        obj = json.loads(obj_text)
                        objects.append(obj)
                        in_object = False
                        current_object = []
                    except:
                        safe_print(f"⚠️  Failed to parse object starting at line containing: {current_object[0][:50]}...")
                        in_object = False
                        current_object = []
                        brace_count = 0
    
    return objects

def fix_json_file(input_file, output_file=None):
    """Fix corrupted JSON file"""
    
    if not os.path.exists(input_file):
        safe_print(f"❌ File not found: {input_file}")
        return False
    
    if output_file is None:
        # Create backup first
        backup_file = f"{input_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(input_file, backup_file)
        output_file = input_file
        safe_print(f"💾 Created backup: {backup_file}")
    
    safe_print(f"🔧 Reading {input_file}...")
    
    try:
        # First try to load as valid JSON
        with open(input_file if output_file != input_file else backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            safe_print(f"✅ File is already valid JSON with {len(data)} entries")
            
            # Still write it out to ensure proper formatting
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
    except json.JSONDecodeError:
        safe_print(f"🔧 JSON is corrupted, attempting to repair...")
    
    # Read raw content
    with open(input_file if output_file != input_file else backup_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract individual objects
    objects = extract_json_objects(content)
    
    safe_print(f"📊 Extracted {len(objects)} valid JSON objects")
    
    # Count URLs
    urls_found = sum(1 for obj in objects if isinstance(obj, dict) and 'url' in obj)
    safe_print(f"🔗 Found {urls_found} objects with URLs")
    
    # Save fixed JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(objects, f, indent=2, ensure_ascii=False)
    
    # Verify the output
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            verify_data = json.load(f)
        safe_print(f"✅ Successfully created valid JSON with {len(verify_data)} entries")
        safe_print(f"💾 Fixed file saved as: {output_file}")
        return True
    except:
        safe_print(f"❌ Failed to create valid JSON")
        return False

def main():
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        input_file = "master2.json"
        output_file = None
    
    fix_json_file(input_file, output_file)

if __name__ == "__main__":
    main()