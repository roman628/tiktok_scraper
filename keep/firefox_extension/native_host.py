#!/opt/homebrew/bin/python3

import sys
import json
import struct
import os
import threading
from pathlib import Path

def send_message(message):
    encoded_message = json.dumps(message).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('I', len(encoded_message)))
    sys.stdout.buffer.write(encoded_message)
    sys.stdout.buffer.flush()

def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    message_length = struct.unpack('I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def add_url_to_file(url):
    try:
        script_dir = Path(__file__).parent.parent
        urls_file = script_dir / 'urls.txt'
        
        if urls_file.exists():
            with open(urls_file, 'r') as f:
                existing_urls = set(line.strip() for line in f if line.strip())
        else:
            existing_urls = set()
        
        if url not in existing_urls:
            with open(urls_file, 'a') as f:
                f.write(f"{url}\n")
            return {"success": True, "message": f"URL added to {urls_file}"}
        else:
            return {"success": True, "message": "URL already exists in file"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    while True:
        try:
            message = read_message()
            if message is None:
                break
                
            if message.get('action') == 'add_url':
                url = message.get('url')
                if url:
                    response = add_url_to_file(url)
                    send_message(response)
                else:
                    send_message({"success": False, "error": "No URL provided"})
            else:
                send_message({"success": False, "error": "Unknown action"})
                
        except Exception as e:
            send_message({"success": False, "error": str(e)})
            break

if __name__ == '__main__':
    main()