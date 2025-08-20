"""Data management for JSON operations, duplicate detection, and file handling."""

import json
import os
import tempfile
import shutil
import fcntl
import platform
from typing import List, Dict, Any, Set, Optional
from pathlib import Path
import threading

class FileLock:
    """Cross-platform file locking."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.lock_file = f"{file_path}.lock"
        self.handle = None
        
    def __enter__(self):
        if platform.system() == 'Windows':
            import msvcrt
            self.handle = open(self.lock_file, 'w')
            while True:
                try:
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except IOError:
                    import time
                    time.sleep(0.1)
        else:
            self.handle = open(self.lock_file, 'w')
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            if platform.system() == 'Windows':
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            try:
                os.remove(self.lock_file)
            except:
                pass

class DataManager:
    """Manages all JSON operations and data persistence."""
    
    def __init__(self, master_file: str = "master2.json"):
        self.master_file = master_file
        self.existing_urls: Set[str] = set()
        self._lock = threading.Lock()
        self._load_existing_urls()
    
    def _load_existing_urls(self):
        """Load existing URLs from master file for duplicate detection."""
        if not os.path.exists(self.master_file):
            return
        
        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'url' in item:
                            self.existing_urls.add(item['url'])
        except (json.JSONDecodeError, IOError):
            # Try to repair if corrupted
            self._repair_json_file()
            self._load_existing_urls()
    
    def is_duplicate(self, url: str) -> bool:
        """Check if URL already exists in dataset."""
        return url in self.existing_urls
    
    def append_to_master(self, data: Dict[str, Any]):
        """Append single entry to master JSON file."""
        self.append_batch_to_master([data])
    
    def append_batch_to_master(self, data_list: List[Dict[str, Any]]):
        """Memory-efficient batch append to master JSON file."""
        if not data_list:
            return
        
        with self._lock:
            with FileLock(self.master_file):
                self._append_batch_efficient(data_list)
                # Update cache
                for item in data_list:
                    if 'url' in item:
                        self.existing_urls.add(item['url'])
    
    def _append_batch_efficient(self, metadata_list: List[Dict[str, Any]]):
        """Internal method for efficient JSON streaming append."""
        if not os.path.exists(self.master_file):
            with open(self.master_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_list, f, indent=2, ensure_ascii=False)
            print(f"Created master file with {len(metadata_list)} entries")
            return
        
        temp_fd, temp_path = tempfile.mkstemp(suffix='.json', dir=os.path.dirname(self.master_file))
        
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as temp_file:
                with open(self.master_file, 'r', encoding='utf-8') as original:
                    first_char = original.read(1)
                    if first_char != '[':
                        # Convert to array format
                        original.seek(0)
                        temp_file.write('[')
                        temp_file.write(original.read().rstrip())
                        temp_file.write(',\n')
                    else:
                        # Stream existing array content
                        temp_file.write('[')
                        has_content = self._stream_existing_content(original, temp_file)
                        if has_content:
                            temp_file.write(',')
                    
                    # Append new items
                    for i, item in enumerate(metadata_list):
                        temp_file.write('\n')
                        json.dump(item, temp_file, indent=2, ensure_ascii=False)
                        if i < len(metadata_list) - 1:
                            temp_file.write(',')
                    temp_file.write('\n]\n')
            
            shutil.move(temp_path, self.master_file)
            print(f"Appended {len(metadata_list)} entries to master file")
            
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    
    def _stream_existing_content(self, original_file, temp_file):
        """Stream existing JSON array content efficiently."""
        buffer = ""
        in_string = False
        escape_next = False
        bracket_depth = 1
        has_content = False
        
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
                        buffer = buffer.rstrip().rstrip(',')
                        if buffer.strip():
                            temp_file.write(buffer)
                            has_content = True
                        break
            else:
                escape_next = False
            
            buffer += char
            
            if len(buffer) > 10000:  # Write in chunks
                temp_file.write(buffer)
                buffer = ""
                has_content = True
        
        if buffer and bracket_depth > 0:
            temp_file.write(buffer.rstrip().rstrip(','))
            has_content = True
        
        return has_content
    
    def _repair_json_file(self) -> bool:
        """Repair corrupted JSON file by extracting valid objects."""
        if not os.path.exists(self.master_file):
            return False
        
        print(f"Attempting to repair {self.master_file}...")
        
        try:
            # Skip backup creation to avoid clutter
            with open(self.master_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            objects = self._extract_json_objects(content)
            
            if objects:
                with open(self.master_file, 'w', encoding='utf-8') as f:
                    json.dump(objects, f, indent=2, ensure_ascii=False)
                print(f"Repaired JSON with {len(objects)} valid entries")
                return True
        except Exception as e:
            print(f"Failed to repair JSON: {e}")
        
        return False
    
    def _extract_json_objects(self, content: str) -> List[Dict[str, Any]]:
        """Extract individual JSON objects from corrupted content."""
        objects = []
        lines = content.split('\n')
        current_object = []
        brace_count = 0
        in_object = False
        
        for line in lines:
            if line.strip().startswith('{') and brace_count == 0:
                in_object = True
                current_object = [line]
                brace_count = line.count('{') - line.count('}')
            elif in_object:
                current_object.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count == 0:
                    try:
                        obj_text = '\n'.join(current_object)
                        obj = json.loads(obj_text)
                        objects.append(obj)
                    except json.JSONDecodeError:
                        # Try removing trailing comma
                        try:
                            obj_text = obj_text.rstrip().rstrip(',')
                            obj = json.loads(obj_text)
                            objects.append(obj)
                        except:
                            pass
                    in_object = False
                    current_object = []
        
        return objects
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the data."""
        stats = {
            'total_entries': len(self.existing_urls),
            'file_size_mb': 0,
            'has_duplicates': False
        }
        
        if os.path.exists(self.master_file):
            stats['file_size_mb'] = os.path.getsize(self.master_file) / 1024 / 1024
        
        return stats