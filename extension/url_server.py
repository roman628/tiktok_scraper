#!/usr/bin/env python3

import http.server
import socketserver
import json
import urllib.parse
from pathlib import Path
import os

class URLHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/add_url':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                # Check if this is a test connection
                if data.get('test'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    response = json.dumps({"success": True, "message": "Connection test successful"})
                    self.wfile.write(response.encode('utf-8'))
                    return
                
                url = data.get('url')
                if url:
                    result = self.add_url_to_file(url)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    response = json.dumps(result)
                    self.wfile.write(response.encode('utf-8'))
                else:
                    self.send_error(400, "No URL provided")
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def add_url_to_file(self, url):
        try:
            # Get the project root directory (parent of extension directory)
            script_dir = Path(__file__).parent.parent
            
            # Create data directory if it doesn't exist
            data_dir = script_dir / 'data'
            data_dir.mkdir(exist_ok=True)
            
            # Path to urls.txt in data directory
            urls_file = data_dir / 'urls.txt'
            
            # Read existing URLs to check for duplicates
            if urls_file.exists():
                with open(urls_file, 'r') as f:
                    existing_urls = set(line.strip() for line in f if line.strip())
            else:
                existing_urls = set()
            
            # Add URL if it's not a duplicate
            if url not in existing_urls:
                with open(urls_file, 'a') as f:
                    f.write(f"{url}\n")
                return {"success": True, "message": f"URL added to data/urls.txt"}
            else:
                return {"success": True, "message": "URL already exists in file"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def log_message(self, format, *args):
        # Suppress default logging to keep console clean
        pass

if __name__ == "__main__":
    PORT = 8765
    print(f"Starting TikTok URL collector server on port {PORT}")
    print(f"URLs will be saved to: data/urls.txt")
    print("Press Ctrl+C to stop")
    
    with socketserver.TCPServer(("", PORT), URLHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped")
            httpd.shutdown()