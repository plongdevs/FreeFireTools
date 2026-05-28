#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import hashlib
import requests
import time
import re
import json
import base64
import socket
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

SECRET_KEY = b"1e5898ccb8dfdd921f9bdea848768b64a201"
AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

def decode_nickname(encoded: str) -> str:
    try:
        raw = base64.b64decode(encoded)
        dec = bytearray()
        for i, b in enumerate(raw): dec.append(b ^ SECRET_KEY[i % len(SECRET_KEY)])
        return dec.decode("utf-8", errors="replace")
    except Exception: return encoded

def aes_encrypt(data: bytes, key=AES_KEY, iv=AES_IV) -> bytes:
    if isinstance(key, str): key = bytes.fromhex(key) if len(key) == 32 else key.encode()
    if isinstance(iv, str):  iv  = bytes.fromhex(iv)  if len(iv)  == 32 else iv.encode()
    if isinstance(key, list) and len(key) > 0: key = key[0]
    if isinstance(iv, list) and len(iv) > 0: iv = iv[0]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))

def aes_decrypt(data: bytes, key=AES_KEY, iv=AES_IV) -> bytes:
    if isinstance(key, str): key = bytes.fromhex(key) if len(key) == 32 else key.encode()
    if isinstance(iv, str):  iv  = bytes.fromhex(iv)  if len(iv)  == 32 else iv.encode()
    if isinstance(key, list) and len(key) > 0: key = key[0]
    if isinstance(iv, list) and len(iv) > 0: iv = iv[0]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(data), AES.block_size)

def parse_proto(data: bytes) -> dict:
    result = {}
    idx = 0
    while idx < len(data):
        try:
            tag = data[idx]; idx += 1
            fn = tag >> 3; wt = tag & 0x07
            if wt == 0:
                val = 0; shift = 0
                while idx < len(data):
                    b = data[idx]; idx += 1
                    val |= (b & 0x7F) << shift
                    if not (b & 0x80): break
                    shift += 7
                if fn in result:
                    if not isinstance(result[fn], list): result[fn] = [result[fn]]
                    result[fn].append(val)
                else: result[fn] = val
            elif wt == 2:
                ln = 0; shift = 0
                while idx < len(data):
                    b = data[idx]; idx += 1
                    ln |= (b & 0x7F) << shift
                    if not (b & 0x80): break
                    shift += 7
                vb = data[idx:idx+ln]; idx += ln
                if fn in result:
                    if not isinstance(result[fn], list): result[fn] = [result[fn]]
                    result[fn].append(vb)
                else: result[fn] = vb
            elif wt == 1:
                idx += 8
            elif wt == 5:
                idx += 4
            else: break
        except: break
    return result

def decode_jwt(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2: return {}
    p = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(p).decode())
        if "nickname" in payload and isinstance(payload["nickname"], str):
            payload["nickname"] = decode_nickname(payload["nickname"])
        return payload
    except: return {}

def convert_time(seconds):
    d, s = divmod(int(seconds), 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}d {h}h {m}m {s}s"

GARENA_HEADERS = {
    "User-Agent": "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip"
}

def send_otp(email, access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
    data = {"email": email, "locale": "en_MA", "region": "IND",
            "app_id": "100067", "access_token": access_token}
    try:
        return requests.post(url, headers=GARENA_HEADERS, data=data)
    except Exception as e:
        return None

def verify_otp(otp, email, access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
    data = {"app_id": "100067", "access_token": access_token, "otp": otp, "email": email}
    return requests.post(url, data=data, headers=GARENA_HEADERS)

def cancel_request(access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
    payload = {'app_id': "100067", 'access_token': access_token}
    try: requests.post(url, data=payload, headers=GARENA_HEADERS)
    except: pass

def extract_eat_from_input(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('http'):
        m = re.search(r'[?&]eat=([a-fA-F0-9]+)', raw)
        if m: return m.group(1)
    return raw

def eat_to_access(eat_token: str) -> str:
    TARGET = "https://api-otrss.garena.com/support/callback/"
    session = requests.Session()
    resp = session.get(TARGET, params={'access_token': eat_token}, allow_redirects=False)
    while resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get('Location', '')
        if not location: break
        if not location.startswith(('http://', 'https://')):
            base = urlparse(TARGET)
            location = base._replace(path=location).geturl()
        resp = session.get(location, allow_redirects=False)
    parsed = urlparse(resp.url)
    params = parse_qs(parsed.query)
    return params.get('access_token', [None])[0]

def _varint(v):
    r = bytearray()
    while v > 0x7F:
        r.append((v & 0x7F) | 0x80); v >>= 7
    r.append(v); return bytes(r)

def _str_field(f, v):
    if isinstance(v, str): v = v.encode()
    return _varint((f << 3) | 2) + _varint(len(v)) + v

def build_login_payload(open_id: str, access_token: str, platform: int) -> bytes:
    now = str(datetime.now())[:19]
    pl = bytearray()
    pl += _str_field(3,  now)
    pl += _str_field(22, open_id)
    pl += _str_field(23, str(platform))
    pl += _str_field(29, access_token)
    pl += _str_field(99, str(platform))
    return bytes(pl)

def build_login_packet_from_jwt(jwt_token: str, key, iv) -> bytes:
    payload = decode_jwt(jwt_token)
    acc_id = int(payload.get('account_id', 0))
    exp = int(payload.get('exp', 0))
    exp_adj = max(exp - 28800, 0)
    
    enc_token = aes_encrypt(jwt_token.encode(), key, iv)
    body_len  = len(enc_token)
    
    acc_hex      = acc_id.to_bytes(8, "big").hex()
    time_hex     = exp_adj.to_bytes(4, "big").hex()
    body_len_hex = body_len.to_bytes(4, "big").hex()
    header_hex = "0115" + acc_hex + time_hex + body_len_hex
    return bytes.fromhex(header_hex) + enc_token

def parse_duration(duration_str: str) -> int:
    """Parse duration string like '1d:2h:30m:10s' to seconds"""
    total = 0
    parts = duration_str.split(':')
    for part in parts:
        if part.endswith('d'):
            total += int(part[:-1]) * 86400
        elif part.endswith('h'):
            total += int(part[:-1]) * 3600
        elif part.endswith('m'):
            total += int(part[:-1]) * 60
        elif part.endswith('s'):
            total += int(part[:-1])
        else:
            total += int(part)
    return total

def _varint(v):
    r = bytearray()
    while v > 0x7F:
        r.append((v & 0x7F) | 0x80); v >>= 7
    r.append(v); return bytes(r)

def _int_field(f, v):
    return _varint((f << 3) | 0) + _varint(v)

def _str_field(f, v):
    if isinstance(v, str): v = v.encode()
    return _varint((f << 3) | 2) + _varint(len(v)) + v

def save_task(task_id, task_data):
    """Save task to tasks.json"""
    try:
        with open('tasks.json', 'r') as f:
            tasks = json.load(f)
    except:
        tasks = []
    
    tasks.append(task_data)
    
    with open('tasks.json', 'w') as f:
        json.dump(tasks, f, indent=2)
    
    return task_id

def get_task_status(task_id):
    """Get task status from tasks.json"""
    try:
        with open('tasks.json', 'r') as f:
            tasks = json.load(f)
        
        for task in tasks:
            if task.get('task_id') == task_id:
                return task
        return None
    except:
        return None

def update_task_status(task_id, status, result=None):
    """Update task status in tasks.json"""
    try:
        with open('tasks.json', 'r') as f:
            tasks = json.load(f)
    except:
        return False
    
    for task in tasks:
        if task.get('task_id') == task_id:
            task['status'] = status
            if result:
                task['result'] = result
            task['updated_at'] = datetime.now().isoformat()
            break
    
    with open('tasks.json', 'w') as f:
        json.dump(tasks, f, indent=2)
    
    return True

def inspect_token(access_token: str):
    url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
    h = {"Connection": "close", "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"}
    r = requests.get(url, headers=h, timeout=10)
    d = r.json()
    if 'error' in d: raise Exception(f"Token lỗi: {d.get('error')}")
    return d.get('open_id'), int(d.get('platform', 8))

def do_major_login(open_id: str, access_token: str, platform: int):
    url = "https://loginbp.ggpolarbear.com/MajorLogin"
    headers = {
        'X-Unity-Version': '2018.4.11f1', 'ReleaseVersion': "OB53",
        'Content-Type': 'application/x-www-form-urlencoded', 'X-GA': 'v1 1',
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)',
        'Host': 'loginbp.ggpolarbear.com',
        'Connection': 'Keep-Alive'
    }
    enc = aes_encrypt(build_login_payload(open_id, access_token, platform))
    resp = requests.post(url, headers=headers, data=enc, verify=False, timeout=10)
    if resp.status_code != 200:
        raise Exception(f"MajorLogin thất bại HTTP {resp.status_code}")
    
    content = resp.content
    for data_to_parse in [content, (lambda: (aes_decrypt(content) if len(content)%16==0 else b""))()]:
        if not data_to_parse: continue
        parsed = parse_proto(data_to_parse)
        token = parsed.get(8)
        if isinstance(token, list): token = token[0]
        if token:
            if isinstance(token, bytes): token = token.decode('utf-8', 'ignore')
            key = parsed.get(22, AES_KEY)
            if isinstance(key, list): key = key[0]
            iv = parsed.get(23, AES_IV)
            if isinstance(iv, list): iv = iv[0]
            return token, key, iv
    raise Exception("Không parse được JWT từ MajorLogin")

def guest_get_access(uid, password):
    url = "https://100067.connect.garena.com/oauth/token"
    data = {
        'grant_type': 'password',
        'app_id': '100067',
        'account': uid,
        'password': hashlib.md5(password.encode()).hexdigest()
    }
    headers = {
        'User-Agent': 'GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=data, headers=headers, timeout=12)
        j = r.json()
        return j.get('open_id'), j.get('access_token')
    except Exception as e:
        return None, None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check_recovery_email', methods=['POST'])
def check_recovery_email():
    try:
        data = request.json
        access_token = data.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        resp = requests.get(url, params={'app_id': "100067", 'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            email = data.get("email", "")
            email_to_be = data.get("email_to_be", "")
            countdown = data.get("request_exec_countdown", 0)
            
            result = {
                'success': True,
                'email': email,
                'email_to_be': email_to_be,
                'countdown': convert_time(countdown),
                'status': 'verified' if email else ('pending' if email_to_be else 'none')
            }
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': f'API Error: {resp.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check_platforms', methods=['POST'])
def check_platforms():
    try:
        data = request.json
        access_token = data.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        url = "https://100067.connect.garena.com/bind/app/platform/info/get"
        resp = requests.get(url, params={'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code not in [200, 201]:
            return jsonify({'success': False, 'error': 'Failed to fetch platform data'})
        
        platform_names = {3:"Facebook", 8:"Gmail", 10:"Apple", 5:"VK", 11:"Twitter (X)", 7:"Huawei"}
        data = resp.json()
        bounded = data.get("bounded_accounts", [])
        available = data.get("available_platforms", [])
        
        bounded_list = []
        for acc in bounded:
            try:
                platform = acc.get('platform')
                ui = acc.get('user_info', {})
                email = ui.get('email', '')
                nick  = ui.get('nickname', '')
                if platform in platform_names:
                    bounded_list.append({
                        'platform': platform_names[platform],
                        'email': email,
                        'nickname': nick
                    })
            except: continue
        
        main_platform = "Unknown"
        for pid, name in platform_names.items():
            if pid not in available:
                main_platform = name
                break
        
        return jsonify({
            'success': True,
            'bounded': bounded_list,
            'main_platform': main_platform
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cancel_recovery_email', methods=['POST'])
def cancel_recovery_email():
    try:
        data = request.json
        access_token = data.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
        resp = requests.post(url, data={'app_id': "100067", 'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code == 200:
            return jsonify({'success': True, 'message': 'Cancelled successfully'})
        else:
            return jsonify({'success': False, 'error': 'No active request found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/revoke_token', methods=['POST'])
def revoke_token():
    try:
        data = request.json
        access_token = data.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        resp = requests.get(f"https://100067.connect.garena.com/oauth/logout?access_token={access_token}")
        if resp.text.strip() == '{"result":0}':
            return jsonify({'success': True, 'message': 'Token revoked'})
        else:
            return jsonify({'success': False, 'error': resp.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/eat_to_access', methods=['POST'])
def eat_to_access_api():
    try:
        data = request.json
        raw = data.get('eat_token')
        if not raw:
            return jsonify({'success': False, 'error': 'EAT token is required'})
        
        eat = extract_eat_from_input(raw)
        if not eat:
            return jsonify({'success': False, 'error': 'Could not extract EAT token'})
        
        access = eat_to_access(eat)
        if access:
            return jsonify({'success': True, 'access_token': access})
        else:
            return jsonify({'success': False, 'error': 'Could not get Access Token'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/eat_to_jwt', methods=['POST'])
def eat_to_jwt_api():
    try:
        data = request.json
        raw = data.get('eat_token')
        if not raw:
            return jsonify({'success': False, 'error': 'EAT token is required'})
        
        eat = extract_eat_from_input(raw)
        if not eat:
            return jsonify({'success': False, 'error': 'Could not extract EAT token'})
        
        access = eat_to_access(eat)
        if not access:
            return jsonify({'success': False, 'error': 'Could not get Access Token'})
        
        open_id, platform = inspect_token(access)
        jwt, _, _ = do_major_login(open_id, access, platform)
        
        dec = decode_jwt(jwt)
        return jsonify({
            'success': True,
            'jwt_token': jwt,
            'decoded': dec
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/access_to_jwt', methods=['POST'])
def access_to_jwt_api():
    try:
        data = request.json
        access_token = data.get('access_token')
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        open_id, platform = inspect_token(access_token)
        jwt, _, _ = do_major_login(open_id, access_token, platform)
        
        dec = decode_jwt(jwt)
        return jsonify({
            'success': True,
            'jwt_token': jwt,
            'decoded': dec
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/guest_to_jwt', methods=['POST'])
def guest_to_jwt_api():
    try:
        data = request.json
        uid = data.get('uid')
        password = data.get('password')
        if not uid or not password:
            return jsonify({'success': False, 'error': 'UID and Password are required'})
        
        open_id, access_token = guest_get_access(uid, password)
        if not open_id or not access_token:
            return jsonify({'success': False, 'error': 'Guest auth failed'})
        
        jwt, _, _ = do_major_login(open_id, access_token, 4)
        dec = decode_jwt(jwt)
        
        return jsonify({
            'success': True,
            'jwt_token': jwt,
            'decoded': dec
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/add_recovery_email', methods=['POST'])
def add_recovery_email():
    try:
        data = request.json
        email = data.get('email')
        access_token = data.get('access_token')
        otp = data.get('otp')
        security_code = data.get('security_code')
        
        if not all([email, access_token, otp, security_code]):
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        if len(security_code) != 6 or not security_code.isdigit():
            return jsonify({'success': False, 'error': 'Security code must be 6 digits'})
        
        cancel_request(access_token)
        
        resp = send_otp(email, access_token)
        if not resp or resp.status_code != 200:
            return jsonify({'success': False, 'error': 'Failed to send OTP'})
        
        vr = verify_otp(otp, email, access_token)
        if vr.status_code != 200:
            return jsonify({'success': False, 'error': 'OTP verification failed'})
        
        verifier_token = vr.json().get("verifier_token")
        if not verifier_token:
            return jsonify({'success': False, 'error': 'No verifier token'})
        
        hashed_password = hashlib.sha256(security_code.encode('utf-8')).hexdigest().upper()
        url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
        data = {
            "app_id": "100067",
            "access_token": access_token,
            "verifier_token": verifier_token,
            "secondary_password": hashed_password,
            "email": email
        }
        br = requests.post(url, data=data, headers=GARENA_HEADERS)
        
        if br.status_code == 200:
            return jsonify({'success': True, 'message': f'Email {email} added successfully'})
        else:
            return jsonify({'success': False, 'error': br.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/spam_log', methods=['POST'])
def spam_log():
    try:
        data = request.json
        access_token = data.get('access_token')
        duration = data.get('duration', '10s')  # Default 10 seconds
        
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        total_seconds = parse_duration(str(duration))
        max_duration = 15 * 24 * 60 * 60  # 15 days in seconds
        if total_seconds <= 0 or total_seconds > max_duration:
            return jsonify({'success': False, 'error': f'Duration must be between 1 second and 15 days'})
        
        # Create task ID
        task_id = f"spam_log_{int(time.time())}_{hash(access_token) % 10000}"
        
        # Save task to queue
        task_data = {
            'task_id': task_id,
            'type': 'spam_log',
            'access_token': access_token,
            'duration': total_seconds,
            'duration_str': str(duration),
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'result': None
        }
        
        save_task(task_id, task_data)
        
        return jsonify({
            'success': True,
            'message': 'Spam log task created',
            'task_id': task_id,
            'status': 'pending',
            'duration': total_seconds
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/task_status/<task_id>', methods=['GET'])
def task_status(task_id):
    try:
        task = get_task_status(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'Task not found'})
        
        return jsonify({
            'success': True,
            'task': task
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/long_bio', methods=['POST'])
def long_bio():
    try:
        data = request.json
        jwt_token = data.get('jwt_token')
        bio_text = data.get('bio_text')
        method = data.get('method', 'jwt')  # jwt, access, guest
        access_token = data.get('access_token')
        uid = data.get('uid')
        password = data.get('password')
        
        if not bio_text:
            return jsonify({'success': False, 'error': 'Bio text is required'})
        
        # Get JWT based on method
        if method == 'access':
            if not access_token:
                return jsonify({'success': False, 'error': 'Access token is required'})
            open_id, platform = inspect_token(access_token)
            jwt_token, _, _ = do_major_login(open_id, access_token, platform)
        elif method == 'guest':
            if not uid or not password:
                return jsonify({'success': False, 'error': 'UID and password are required'})
            open_id, at = guest_get_access(uid, password)
            if not open_id or not at:
                return jsonify({'success': False, 'error': 'Guest login failed'})
            jwt_token, _, _ = do_major_login(open_id, at, 4)
        elif method == 'jwt':
            if not jwt_token:
                return jsonify({'success': False, 'error': 'JWT token is required'})
        else:
            return jsonify({'success': False, 'error': 'Invalid method'})
        
        # Build Protobuf Payload
        pl = bytearray()
        pl += _int_field(2, 17)
        pl += _str_field(5, b'')
        pl += _str_field(6, b'')
        pl += _str_field(8, bio_text)
        pl += _int_field(9, 1)
        pl += _str_field(11, b'')
        pl += _str_field(12, b'')
        
        enc = aes_encrypt(bytes(pl))
        
        headers = {
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB53",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {jwt_token}"
        }
        
        r = requests.post("https://clientbp.ggpolarbear.com/UpdateSocialBasicInfo", 
                         headers=headers, data=enc, timeout=20, verify=True)
        
        if r.status_code == 200:
            return jsonify({'success': True, 'message': 'Bio updated successfully'})
        elif r.status_code == 401:
            return jsonify({'success': False, 'error': 'JWT invalid or expired'})
        else:
            return jsonify({'success': False, 'error': f'Server error: {r.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send_otp_unbind', methods=['POST'])
def send_otp_unbind():
    try:
        data = request.json
        email = data.get('email')
        access_token = data.get('access_token')
        
        if not all([email, access_token]):
            return jsonify({'success': False, 'error': 'Email và access token là bắt buộc'})
        
        resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                           headers=GARENA_HEADERS,
                           data={"email": email, "locale": "en_MA", "region": "IND", 
                                  "app_id": "100067", "access_token": access_token})
        
        if '"result":0' in resp.text.replace(" ", ""):
            return jsonify({'success': True, 'message': 'OTP đã gửi đến email của bạn'})
        else:
            return jsonify({'success': False, 'error': 'Gửi OTP thất bại'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send_otp_change_old', methods=['POST'])
def send_otp_change_old():
    try:
        data = request.json
        old_email = data.get('old_email')
        access_token = data.get('access_token')
        
        if not all([old_email, access_token]):
            return jsonify({'success': False, 'error': 'Email cũ và access token là bắt buộc'})
        
        resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                           headers=GARENA_HEADERS,
                           data={'email': old_email, 'locale': 'en_MA', 'region': 'IND', 
                                  'app_id': '100067', 'access_token': access_token})
        
        if '"result":0' in resp.text.replace(" ", ""):
            return jsonify({'success': True, 'message': 'OTP đã gửi đến email cũ'})
        else:
            return jsonify({'success': False, 'error': 'Gửi OTP thất bại'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/send_otp_change_new', methods=['POST'])
def send_otp_change_new():
    try:
        data = request.json
        new_email = data.get('new_email')
        access_token = data.get('access_token')
        
        if not all([new_email, access_token]):
            return jsonify({'success': False, 'error': 'Email mới và access token là bắt buộc'})
        
        resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                           headers=GARENA_HEADERS,
                           data={'email': new_email, 'locale': 'en_MA', 'region': 'IND', 
                                  'app_id': '100067', 'access_token': access_token})
        
        if '"result":0' in resp.text.replace(" ", ""):
            return jsonify({'success': True, 'message': 'OTP đã gửi đến email mới'})
        else:
            return jsonify({'success': False, 'error': 'Gửi OTP thất bại'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unbind_email', methods=['POST'])
def unbind_email():
    try:
        data = request.json
        email = data.get('email')
        access_token = data.get('access_token')
        method = data.get('method', 'otp')  # otp or password
        otp = data.get('otp')
        security_code = data.get('security_code')
        
        if not all([email, access_token]):
            return jsonify({'success': False, 'error': 'Email and access token are required'})
        
        identity_token = None
        
        if method == 'otp':
            if not otp:
                return jsonify({'success': False, 'error': 'OTP is required'})
            # Send OTP
            resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                               headers=GARENA_HEADERS,
                               data={"email": email, "locale": "en_MA", "region": "IND", 
                                      "app_id": "100067", "access_token": access_token})
            if '"result":0' not in resp.text.replace(" ", ""):
                return jsonify({'success': False, 'error': 'OTP send failed'})
            # Verify OTP
            r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                             headers=GARENA_HEADERS,
                             data={"email": email, "otp": otp, "app_id": "100067", 
                                    "access_token": access_token})
            identity_token = r.json().get("identity_token")
        elif method == 'password':
            if not security_code or len(security_code) != 6 or not security_code.isdigit():
                return jsonify({'success': False, 'error': 'Security code must be 6 digits'})
            hashed_sp = hashlib.sha256(security_code.encode('utf-8')).hexdigest().upper()
            r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                             headers=GARENA_HEADERS,
                             data={"email": email, "secondary_password": hashed_sp, 
                                    "app_id": "100067", "access_token": access_token})
            identity_token = r.json().get("identity_token")
        
        if not identity_token:
            return jsonify({'success': False, 'error': 'Failed to get identity token'})
        
        # Create unbind request
        resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_unbind_request",
                           headers=GARENA_HEADERS,
                           data={"app_id": "100067", "access_token": access_token, 
                                  "identity_token": identity_token})
        
        if '"result":0' in resp.text.replace(" ", ""):
            return jsonify({'success': True, 'message': 'Unbind request created successfully'})
        else:
            return jsonify({'success': False, 'error': resp.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/change_bind_email', methods=['POST'])
def change_bind_email():
    try:
        data = request.json
        access_token = data.get('access_token')
        old_email = data.get('old_email')
        new_email = data.get('new_email')
        method = data.get('method', 'otp')  # otp or password
        otp_old = data.get('otp_old')
        security_code = data.get('security_code')
        otp_new = data.get('otp_new')
        
        if not all([access_token, old_email, new_email]):
            return jsonify({'success': False, 'error': 'Access token, old email, and new email are required'})
        
        identity_token = None
        
        if method == 'otp':
            if not otp_old:
                return jsonify({'success': False, 'error': 'OTP for old email is required'})
            # Send OTP to old email
            requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                        headers=GARENA_HEADERS,
                        data={'email': old_email, 'locale': 'en_MA', 'region': 'IND', 
                               'app_id': '100067', 'access_token': access_token})
            # Verify old OTP
            r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                             headers=GARENA_HEADERS,
                             data={'email': old_email, 'app_id': '100067', 
                                    'access_token': access_token, 'otp': otp_old})
            identity_token = r.json().get("identity_token")
        elif method == 'password':
            if not security_code or len(security_code) != 6 or not security_code.isdigit():
                return jsonify({'success': False, 'error': 'Security code must be 6 digits'})
            hashed_sp = hashlib.sha256(security_code.encode('utf-8')).hexdigest().upper()
            r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                             headers=GARENA_HEADERS,
                             data={'email': old_email, 'secondary_password': hashed_sp, 
                                    'app_id': '100067', 'access_token': access_token})
            identity_token = r.json().get("identity_token")
        
        if not identity_token:
            return jsonify({'success': False, 'error': 'Failed to get identity token'})
        
        # Send OTP to new email
        requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                     headers=GARENA_HEADERS,
                     data={'email': new_email, 'locale': 'en_MA', 'region': 'IND', 
                            'app_id': '100067', 'access_token': access_token})
        
        if not otp_new:
            return jsonify({'success': False, 'error': 'OTP for new email is required'})
        
        # Verify new OTP
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_otp",
                        headers=GARENA_HEADERS,
                        data={'email': new_email, 'app_id': '100067', 
                               'access_token': access_token, 'otp': otp_new})
        verifier_token = r.json().get("verifier_token")
        
        if not verifier_token:
            return jsonify({'success': False, 'error': 'Failed to get verifier token'})
        
        # Create rebind request
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_rebind_request",
                        headers=GARENA_HEADERS,
                        data={'identity_token': identity_token, 'email': new_email, 
                               'app_id': '100067', 'verifier_token': verifier_token, 
                               'access_token': access_token})
        
        if '"result":0' in r.text.replace(" ", ""):
            return jsonify({'success': True, 'message': 'Email rebind created successfully'})
        else:
            return jsonify({'success': False, 'error': r.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
