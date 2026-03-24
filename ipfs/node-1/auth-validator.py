#koneksi01@ubuntu:~$ cat /usr/local/bin/auth-validator.py
#!/usr/bin/env python3
import sys
import os
import urllib.request
import urllib.error
import ssl

def validate_auth():
    # Get headers from environment variables (nginx sets these)
    auth = os.environ.get('HTTP_AUTHORIZATION', '')
    client_id = os.environ.get('HTTP_CLIENT_ID', '')
    client_secret = os.environ.get('HTTP_CLIENT_SECRET', '')
    environment = os.environ.get('HTTP_ENVIRONMENT', '')
    
    # Check static Bearer token first
    if auth == 'Bearer uqvT3vJkqtLqyRZB6sXvHdteukQtqkkN':
        return 200
    
    # Check if environment is provided for other auth methods
    if not environment:
        return 401
    
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
    
    # Make request (ignore SSL verification for simplicity)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
            return response.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 500

if __name__ == '__main__':
    code = validate_auth()
    sys.exit(0 if code == 200 else 1)