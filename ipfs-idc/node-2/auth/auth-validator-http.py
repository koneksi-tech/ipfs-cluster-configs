#!/usr/bin/env python3
"""
Minimal HTTP server for nginx auth_request. Reads request headers,
sets env, runs auth-validator.py, returns 200 or 401.
Run on 127.0.0.1:8888 (same as Server 1; override with AUTH_VALIDATOR_PORT). Use with nginx auth_request.
"""
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get('AUTH_VALIDATOR_PORT', '8888'))
VALIDATOR = os.environ.get('AUTH_VALIDATOR_SCRIPT', '/usr/local/bin/auth-validator.py')


class AuthHandler(BaseHTTPRequestHandler):
    def _auth(self):
        env = os.environ.copy()
        env['HTTP_AUTHORIZATION'] = self.headers.get('Authorization', '')
        env['HTTP_CLIENT_ID'] = self.headers.get('Client-ID', '')
        env['HTTP_CLIENT_SECRET'] = self.headers.get('Client-Secret', '')
        env['HTTP_ENVIRONMENT'] = self.headers.get('Environment', '')
        try:
            r = subprocess.run(
                [VALIDATOR],
                env=env,
                capture_output=True,
                timeout=10,
            )
            code = 200 if r.returncode == 0 else 401
        except Exception:
            code = 500
        self.send_response(code)
        self.end_headers()

    def do_GET(self):
        self._auth()

    def do_POST(self):
        self._auth()

    def log_message(self, format, *args):
        pass  # quiet


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), AuthHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
