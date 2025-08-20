import json
import os
import tempfile
import shutil


def append_batch_to_master_json_efficient(metadata_list, master_file_path):
    """Memory-efficient version that streams JSON data instead of loading all into memory"""
    master_path = master_file_path
    
    # If file doesn't exist, create it with the new data
    if not os.path.exists(master_path):
        with open(master_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_list, f, indent=2, ensure_ascii=False)
        print(f"📎 Created master file with {len(metadata_list)} videos")
        return
    
    # For existing files, use a streaming approach
    temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir=os.path.dirname(master_path))
    
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_file:
            with open(master_path, 'r', encoding='utf-8') as original_file:
                # Read the opening bracket
                first_char = original_file.read(1)
                if first_char != '[':
                    # File doesn't start with array, convert it
                    original_file.seek(0)
                    temp_file.write('[')
                    temp_file.write(original_file.read().rstrip())
                    temp_file.write(',\n')
                    for i, item in enumerate(metadata_list):
                        json.dump(item, temp_file, indent=2, ensure_ascii=False)
                        if i < len(metadata_list) - 1:
                            temp_file.write(',\n')
                    temp_file.write('\n]')
                else:
                    # File is already an array, append to it
                    temp_file.write('[')
                    
                    # Stream existing items
                    buffer = ""
                    in_string = False
                    escape_next = False
                    bracket_depth = 1
                    item_count = 0
                    
                    while bracket_depth > 0:
                        char = original_file.read(1)
                        if not char:
                            break
                            
                        if not escape_next:
                            if char == '"' and not in_string:
                                in_string = True
                            elif char == '"' and in_string:
                                in_string = False
                            elif char == '\\' and in_string:
                                escape_next = True
                            elif char == '[' and not in_string:
                                bracket_depth += 1
                            elif char == ']' and not in_string:
                                bracket_depth -= 1
                                if bracket_depth == 0:
                                    # End of array
                                    buffer = buffer.rstrip()
                                    if buffer and not buffer.endswith(','):
                                        temp_file.write(buffer)
                                        if buffer.strip():
                                            temp_file.write(',')
                                    break
                        else:
                            escape_next = False
                        
                        buffer += char
                        
                        # Write buffer when we have a complete item
                        if len(buffer) > 10000:  # Write in chunks
                            temp_file.write(buffer)
                            buffer = ""
                    
                    # Write any remaining buffer
                    if buffer:
                        temp_file.write(buffer)
                    
                    # Append new items
                    temp_file.write('\n')
                    for i, item in enumerate(metadata_list):
                        temp_file.write('  ')
                        json.dump(item, temp_file, indent=2, ensure_ascii=False)
                        if i < len(metadata_list) - 1:
                            temp_file.write(',\n')
                    
                    temp_file.write('\n]')
        
        # Replace original file with temp file
        shutil.move(temp_path, master_path)
        print(f"📎 Appended {len(metadata_list)} videos to master file")
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e