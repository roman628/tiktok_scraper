#!/usr/bin/env python3

import http.server
import socketserver
import json
import urllib.parse
from pathlib import Path
import os
import toml
import urllib.request
import urllib.error

class URLHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/update_token':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                ms_token = data.get('ms_token')
                if ms_token:
                    result = self.update_ms_token(ms_token)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    response = json.dumps(result)
                    self.wfile.write(response.encode('utf-8'))
                else:
                    self.send_error(400, "No MS_TOKEN provided")
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path == '/add_url':
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
                ms_token = data.get('ms_token')
                
                # If MS_TOKEN is provided with URL, update it
                if ms_token:
                    self.update_ms_token(ms_token)
                
                if url:
                    # Validate URL first
                    print(f"Validating URL: {url}")
                    if self.validate_tiktok_url(url):
                        print(f"✓ Valid URL: {url}")
                        result = self.add_url_to_file(url)
                    else:
                        print(f"✗ Invalid URL: {url}")
                        result = {"success": False, "message": "Invalid TikTok URL - video may not exist or be accessible"}
                    
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

    def validate_tiktok_url(self, url):
        """Validate TikTok URL using oembed endpoint"""
        try:
            # Construct oembed URL
            oembed_url = f"https://www.tiktok.com/oembed?url={urllib.parse.quote(url)}"
            
            # Make request to oembed endpoint
            req = urllib.request.Request(oembed_url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                # If we get valid JSON with title, the video exists
                if data.get('title') or data.get('author_name'):
                    return True
            return False
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError):
            # Any error means the URL is invalid
            return False
        except Exception:
            # For any other unexpected errors, assume invalid
            return False
    
    def update_ms_token(self, ms_token):
        try:
            # Get the project root directory (parent of extension directory)
            script_dir = Path(__file__).parent.parent
            config_file = script_dir / 'config.toml'
            template_file = script_dir / 'assets' / 'config.template.toml'
            
            # Read existing config
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = toml.load(f)
            else:
                # Try to load from template, otherwise use minimal structure
                if template_file.exists():
                    with open(template_file, 'r') as f:
                        config = toml.load(f)
                else:
                    # Fallback to minimal structure if template not found
                    config = {'tiktok': {}}
            
            # Update MS_TOKEN
            config['tiktok']['ms_token'] = ms_token
            
            # Write updated config
            with open(config_file, 'w') as f:
                toml.dump(config, f)
            
            return {"success": True, "message": f"MS_TOKEN updated in config.toml"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run a simple HTTP server to collect TikTok URLs.")
    parser.add_argument('--host', type=str, default='0.0.0.0', 
                        help='Host address to bind to. Defaults to 0.0.0.0.')
    parser.add_argument('--port', type=int, default=8765, 
                        help='Port to listen on. Defaults to 8765.')
    args = parser.parse_args()

    HOST = args.host
    PORT = args.port

    print(f"Starting TikTok URL collector server...")
    # Display Tailscale IP if available, otherwise show host
    if HOST == '0.0.0.0':
        print(f"Listening on all interfaces. Port: {PORT}")
        print(f"Connect from other devices using the machine's local or Tailscale IP.")
    else:
        print(f"Listening on: http://{HOST}:{PORT}")

    print(f"URLs will be saved to: data/urls.txt")
    print("Press Ctrl+C to stop")
    
    # Allow port reuse
    socketserver.TCPServer.allow_reuse_address = True
    
    try:
        with socketserver.TCPServer((HOST, PORT), URLHandler) as httpd:
            httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\nError: Port {PORT} or Host {HOST} is already in use.")
            print("Please stop the other process or use a different port/host.")
        elif "Cannot assign requested address" in str(e):
            print(f"\nError: Cannot assign requested address '{HOST}'.")
            print("Please check if the IP address is correct and available on this machine.")
        else:
            print(f"\nError starting server: {e}")
    except KeyboardInterrupt:
        print("\nServer stopped")

