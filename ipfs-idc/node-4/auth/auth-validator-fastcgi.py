#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error
import json

class AuthHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Get headers
        auth = self.headers.get('Authorization', '')
        client_id = self.headers.get('Client-ID', '')
        client_secret = self.headers.get('Client-Secret', '')
        environment = self.headers.get('Environment', '')
        
        # Check static Bearer token first
        if auth == 'Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN':
            self.send_response(200)
            self.end_headers()
            return
        
        # Check if environment is provided for other auth methods
        if not environment:
            self.send_response(401)
            self.end_headers()
            return
        
        # Determine validation endpoint
        #if environment == 'uat':
        #    url = 'https://uat.koneksi.co.kr/auth/validate'
        #else:
        #    url = 'https://staging.koneksi.co.kr/auth/validate'


        if environment == 'production':
            url = 'https://api.koneksi.co.kr/auth/validate'
        elif environment == 'uat':
            url = 'https://uat.koneksi.co.kr/auth/validate'
        elif environment == 'staging':
            url = 'https://staging.koneksi.co.kr/auth/validate'
        else:
            return 401

        
        # Prepare request
        req = urllib.request.Request(url, method='POST')
        if auth:
            req.add_header('Authorization', auth)
        if client_id:
            req.add_header('Client-ID', client_id)
        if client_secret:
            req.add_header('Client-Secret', client_secret)
        
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                self.send_response(200)
                self.end_headers()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Disable logging

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8888), AuthHandler)
    server.serve_forever()
