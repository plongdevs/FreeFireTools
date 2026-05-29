#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, session
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
import random
import uuid
import os
from google.protobuf.timestamp_pb2 import Timestamp

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this-in-production"

SECRET_KEY = b"1e5898ccb8dfdd921f9bdea848768b64a201"
AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

# Firebase configuration
FIREBASE_URL = "https://freefiretools-a5470-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_SECRET = "bIIZjhwOHgrkxLawK2Lbcfbdd75zxQQ3JVqWQC4b"

def firebase_get(path):
    """Get data from Firebase"""
    url = f"{FIREBASE_URL}/{path}.json?auth={FIREBASE_SECRET}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

def firebase_set(path, data):
    """Set data in Firebase"""
    url = f"{FIREBASE_URL}/{path}.json?auth={FIREBASE_SECRET}"
    response = requests.put(url, json=data)
    return response.status_code == 200

def firebase_update(path, data):
    """Update data in Firebase"""
    url = f"{FIREBASE_URL}/{path}.json?auth={FIREBASE_SECRET}"
    response = requests.patch(url, json=data)
    return response.status_code == 200

def load_users():
    try:
        users = firebase_get('users')
        return users if users else {}
    except:
        return {}

def save_users(users):
    firebase_set('users', users)

def load_usage():
    try:
        usage = firebase_get('usage')
        return usage if usage else {}
    except:
        return {}

def save_usage(usage):
    firebase_set('usage', usage)

def get_user_usage(username):
    usage = load_usage()
    return usage.get(username, {'ban7': 0, 'spam_log': 0, 'is_pro': False})

def update_user_usage(username, feature):
    usage = load_usage()
    if username not in usage:
        usage[username] = {'ban7': 0, 'spam_log': 0, 'is_pro': False}
    usage[username][feature] = usage[username].get(feature, 0) + 1
    save_usage(usage)
    return usage[username]

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

# ---------------- SimpleProtobuf Class for Ban 7 ---------------- #
class SimpleProtobuf:
    @staticmethod
    def encode_varint(value):
        result = bytearray()
        while value > 0x7F:
            result.append((value & 0x7F) | 0x80)
            value >>= 7
        result.append(value & 0x7F)
        return bytes(result)   

    @staticmethod
    def decode_varint(data, start_index=0):
        value = 0
        shift = 0
        index = start_index
        while index < len(data):
            byte = data[index]
            index += 1
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return value, index    

    @staticmethod
    def parse_protobuf(data):
        result = {}
        index = 0
        
        while index < len(data):
            if index >= len(data):
                break
            tag = data[index]
            field_num = tag >> 3
            wire_type = tag & 0x07
            index += 1            
            if wire_type == 0:
                value, index = SimpleProtobuf.decode_varint(data, index)
                result[field_num] = value
            elif wire_type == 2:
                length, index = SimpleProtobuf.decode_varint(data, index)
                if index + length <= len(data):
                    value_bytes = data[index:index + length]
                    index += length
                    try:
                        result[field_num] = value_bytes.decode('utf-8')
                    except:
                        result[field_num] = value_bytes
            else:
                break
        
        return result    

    @staticmethod
    def encode_string(field_number, value):
        if isinstance(value, str):
            value = value.encode('utf-8')        
        result = bytearray()
        result.extend(SimpleProtobuf.encode_varint((field_number << 3) | 2))
        result.extend(SimpleProtobuf.encode_varint(len(value)))
        result.extend(value)
        return bytes(result)   

    @staticmethod
    def encode_int32(field_number, value):
        result = bytearray()
        result.extend(SimpleProtobuf.encode_varint((field_number << 3) | 0))
        result.extend(SimpleProtobuf.encode_varint(value))
        return bytes(result)   

    @staticmethod
    def create_login_payload(open_id, access_token, platform):
        p = str(platform)
        random_ip = f"223.191.{random.randint(1,255)}.{random.randint(1,255)}"
        random_device = f"Fuck Garena Free Fire"

        payload = bytearray()
        payload.extend(SimpleProtobuf.encode_string(3,  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        payload.extend(SimpleProtobuf.encode_string(4,  "free fire"))
        payload.extend(SimpleProtobuf.encode_int32 (5,  1))
        payload.extend(SimpleProtobuf.encode_string(7,  "2.124.1"))
        payload.extend(SimpleProtobuf.encode_string(8,  "Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)"))
        payload.extend(SimpleProtobuf.encode_string(9,  "Handheld"))
        payload.extend(SimpleProtobuf.encode_string(10, "Verizon"))
        payload.extend(SimpleProtobuf.encode_string(11, "WIFI"))
        payload.extend(SimpleProtobuf.encode_int32 (12, 1920))
        payload.extend(SimpleProtobuf.encode_int32 (13, 1080))
        payload.extend(SimpleProtobuf.encode_string(14, "280"))
        payload.extend(SimpleProtobuf.encode_string(15, "ARM64 FP ASIMD AES VMH | 2865 | 4"))
        payload.extend(SimpleProtobuf.encode_int32 (16, 3003))
        payload.extend(SimpleProtobuf.encode_string(17, "Adreno (TM) 640"))
        payload.extend(SimpleProtobuf.encode_string(18, "OpenGL ES 3.1 v1.46"))
        payload.extend(SimpleProtobuf.encode_string(19, random_device))
        payload.extend(SimpleProtobuf.encode_string(20, random_ip))
        payload.extend(SimpleProtobuf.encode_string(21, "en"))
        payload.extend(SimpleProtobuf.encode_string(22, open_id))
        payload.extend(SimpleProtobuf.encode_string(23, p))
        payload.extend(SimpleProtobuf.encode_string(24, "Handheld"))
        payload.extend(SimpleProtobuf.encode_string(25, "samsung SM-G9650"))
        payload.extend(SimpleProtobuf.encode_int32 (30, 1))
        payload.extend(SimpleProtobuf.encode_string(41, "Verizon"))
        payload.extend(SimpleProtobuf.encode_string(42, "WIFI"))
        payload.extend(SimpleProtobuf.encode_string(57, "7428b253defc164018c604a1ebbfebdf"))
        payload.extend(SimpleProtobuf.encode_int32 (60, 2019118695))
        payload.extend(SimpleProtobuf.encode_int32 (61, 36235))
        payload.extend(SimpleProtobuf.encode_int32 (62, 31335))
        payload.extend(SimpleProtobuf.encode_int32 (63, 2519))
        payload.extend(SimpleProtobuf.encode_int32 (64, 703))
        payload.extend(SimpleProtobuf.encode_int32 (65, 25010))
        payload.extend(SimpleProtobuf.encode_int32 (66, 26628))
        payload.extend(SimpleProtobuf.encode_int32 (67, 32992))
        payload.extend(SimpleProtobuf.encode_int32 (73, 3))
        payload.extend(SimpleProtobuf.encode_string(74, "/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/lib/arm64"))
        payload.extend(SimpleProtobuf.encode_int32 (76, 1))
        payload.extend(SimpleProtobuf.encode_string(77, "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-YPKM8jHEwAJlhpmhDhv5MQ==/base.apk"))
        payload.extend(SimpleProtobuf.encode_int32 (78, 3))
        payload.extend(SimpleProtobuf.encode_int32 (79, 2))
        payload.extend(SimpleProtobuf.encode_string(81, "64"))
        payload.extend(SimpleProtobuf.encode_string(83, "2019118695"))
        payload.extend(SimpleProtobuf.encode_int32 (85, 1))
        payload.extend(SimpleProtobuf.encode_string(86, "OpenGLES2"))
        payload.extend(SimpleProtobuf.encode_int32 (87, 16383))
        payload.extend(SimpleProtobuf.encode_int32 (88, 4))
        payload.extend(SimpleProtobuf.encode_string(90, "Fuck Garena Free Fire"))
        payload.extend(SimpleProtobuf.encode_string(91, "android"))
        payload.extend(SimpleProtobuf.encode_int32 (92, 13564))
        payload.extend(SimpleProtobuf.encode_string(93, "android"))
        payload.extend(SimpleProtobuf.encode_string(94, "Fuck Garena Free Fire"))
        payload.extend(SimpleProtobuf.encode_int32 (97, 1))
        payload.extend(SimpleProtobuf.encode_int32 (98, 1))
        payload.extend(SimpleProtobuf.encode_string(99,  p))
        payload.extend(SimpleProtobuf.encode_string(100, p))
        payload.extend(SimpleProtobuf.encode_string(102, ""))
        return bytes(payload)

def b64url_decode(input_str: str) -> bytes:
    rem = len(input_str) % 4
    if rem:
        input_str += '=' * (4 - rem)
    return base64.urlsafe_b64decode(input_str)

def get_available_room(input_text):
    try:
        data = bytes.fromhex(input_text)
        result = {}
        index = 0
        
        while index < len(data):
            if index >= len(data):
                break                
            tag = data[index]
            field_num = tag >> 3
            wire_type = tag & 0x07
            index += 1            
            if wire_type == 0:
                value = 0
                shift = 0
                while index < len(data):
                    byte = data[index]
                    index += 1
                    value |= (byte & 0x7F) << shift
                    if not (byte & 0x80):
                        break
                    shift += 7
                result[str(field_num)] = {"wire_type": "varint", "data": value}                
            elif wire_type == 2:
                length = 0
                shift = 0
                while index < len(data):
                    byte = data[index]
                    index += 1
                    length |= (byte & 0x7F) << shift
                    if not (byte & 0x80):
                        break
                    shift += 7                
                if index + length <= len(data):
                    value_bytes = data[index:index + length]
                    index += length
                    try:
                        value_str = value_bytes.decode('utf-8')
                        result[str(field_num)] = {"wire_type": "string", "data": value_str}
                    except:
                        result[str(field_num)] = {"wire_type": "bytes", "data": value_bytes.hex()}
            else:
                break                
        return json.dumps(result)
    except Exception as e:
        return None

def extract_jwt_payload_dict(jwt_s: str):
    try:
        parts = jwt_s.split('.')
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        payload_bytes = b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8', errors='ignore'))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return None

def encrypt_packet(hex_string: str, aes_key, aes_iv) -> str:
    if isinstance(aes_key, str):
        aes_key = bytes.fromhex(aes_key)
    if isinstance(aes_iv, str):
        aes_iv = bytes.fromhex(aes_iv)   
    data = bytes.fromhex(hex_string)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    return encrypted.hex()

def build_start_packet(account_id: int, timestamp: int, jwt: str, key, iv) -> str:
    try:
        encrypted = encrypt_packet(jwt.encode().hex(), key, iv)
        head_len = hex(len(encrypted) // 2)[2:]
        ide_hex = hex(int(account_id))[2:]
        zeros = "0" * (16 - len(ide_hex))
        timestamp_hex = hex(timestamp)[2:].zfill(2)
        head = f"0115{zeros}{ide_hex}{timestamp_hex}00000{head_len}"
        start_packet = head + encrypted
        
        return start_packet
    except Exception as e:
        return None

def send_once(remote_ip, remote_port, payload_bytes, recv_timeout=3.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(recv_timeout)
    try:
        s.connect((remote_ip, remote_port))
        s.sendall(payload_bytes)
        
        chunks = []
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
        except socket.timeout:
            pass
        return b"".join(chunks)
    finally:
        s.close()

def process_ban7(access_token):
    try:
        # Step 1: Inspect token
        inspect_url = f"https://100067.connect.garena.com/oauth/token/inspect?token={access_token}"
        inspect_headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)"
        }

        try:
            resp = requests.get(inspect_url, headers=inspect_headers, timeout=10)
            data = resp.json()
            if 'error' in data:
                return {"success": False, "message": f"Token error: {data.get('error')}"}
        except Exception as e:
            return {"success": False, "message": f"Failed to inspect token: {str(e)}"}

        NEW_OPEN_ID = data.get('open_id')
        platform_ = data.get('platform')

        # Step 2: MajorLogin
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        MajorLogin_url = "https://loginbp.ggpolarbear.com/MajorLogin"
        MajorLogin_headers = {
            "Host": "loginbp.ggpolarbear.com",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-G991B Build/RP1A.200720.012)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/octet-stream",
            "Expect": "100-continue",
            "X-GA": "v1 1",
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB53"
        }

        data_pb = SimpleProtobuf.create_login_payload(NEW_OPEN_ID, access_token, str(platform_))
        data_padded = pad(data_pb, 16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        enc_data = cipher.encrypt(data_padded)

        try:
            response = requests.post(MajorLogin_url, headers=MajorLogin_headers, data=enc_data, timeout=15)
            if not response.ok:
                return {"success": False, "message": f"MajorLogin error: {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"MajorLogin failed: {str(e)}"}

        # Step 3: Parse MajorLogin response
        resp_enc = response.content
        cipher_resp = AES.new(key, AES.MODE_CBC, iv)
        
        try:
            resp_dec = unpad(cipher_resp.decrypt(resp_enc), 16)
            parsed_data = SimpleProtobuf.parse_protobuf(resp_dec)
        except Exception:
            parsed_data = SimpleProtobuf.parse_protobuf(resp_enc)

        # Get timestamp
        field_21_value = parsed_data.get(21, None)
        if field_21_value:
            ts = Timestamp()
            ts.FromNanoseconds(field_21_value)
            timetamp = ts.seconds * 1_000_000_000 + ts.nanos
        else:
            # Fallback to JWT exp
            return {"success": False, "message": "Could not get timestamp from response"}

        # Step 4: GetLoginData
        GetLoginData_resURL = "https://clientbp.ggpolarbear.com/GetLoginData"
        GetLoginData_res_headers = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {access_token}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB53',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 11; SM-G991B Build/RP1A.200720.012)',
            'Host': 'clientbp.ggpolarbear.com',
            'Connection': 'close',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        try:
            r2 = requests.post(GetLoginData_resURL, headers=GetLoginData_res_headers, data=enc_data, timeout=12, verify=False)
            if r2.status_code != 200:
                return {"success": False, "message": f"GetLoginData error: {r2.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"GetLoginData failed: {str(e)}"}

        # Step 5: Parse server address
        online_ip = None
        online_port = None

        try:
            x = r2.content.hex()
            json_result = get_available_room(x)

            if json_result:
                parsed_data_login = json.loads(json_result)
                if '14' in parsed_data_login and 'data' in parsed_data_login['14']:
                    online_address = parsed_data_login['14']['data']
                    parts = online_address.rsplit(":", 1)
                    online_ip = parts[0]
                    online_port = int(parts[1])
                else:
                    return {"success": False, "message": "Could not find server address"}
            else:
                return {"success": False, "message": "Failed to parse GetLoginData response"}
        except Exception as e:
            return {"success": False, "message": f"Error processing response: {str(e)}"}

        # Step 6: Build and send packet
        account_id = int(extract_jwt_payload_dict(access_token).get("account_id", 0))
        final_token_hex = build_start_packet(
            account_id=account_id,
            timestamp=timetamp,
            jwt=access_token,
            key=key,
            iv=iv)

        if not final_token_hex:
            return {"success": False, "message": "Failed to build packet"}

        try:
            payload_bytes = bytes.fromhex(final_token_hex)
            response = send_once(online_ip, online_port, payload_bytes, recv_timeout=5.0)
            if response:
                return {"success": True, "account_id": account_id, "open_id": NEW_OPEN_ID, "platform": platform_, "data": response.hex()}
            else:
                return {"success": False, "message": "No response from server"}
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

    except Exception as e:
        return {"success": False, "message": f"Unexpected error: {str(e)}"}

@app.route('/api/ban7', methods=['POST'])
def ban7():
    try:
        # Check if user is logged in
        if 'logged_in' not in session or not session['logged_in']:
            return jsonify({'success': False, 'error': 'Bạn cần đăng nhập để sử dụng tính năng này'})
        
        username = session.get('username')
        usage = get_user_usage(username)
        
        # Check usage limit (1 use for free users)
        if not usage.get('is_pro', False) and usage.get('ban7', 0) >= 1:
            return jsonify({
                'success': False,
                'error': 'Bạn đã dùng hết lượt sử dụng miễn phí. Mua gói Pro tại @minhdevtcp để dùng không giới hạn'
            })
        
        data = request.json
        access_token = data.get('access_token')
        
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token là bắt buộc'})
        
        result = process_ban7(access_token)
        
        if result.get('success'):
            update_user_usage(username, 'ban7')
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')
        
        if not all([email, username, password]):
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password must be at least 6 characters'})
        
        users = load_users()
        
        if username in users:
            return jsonify({'success': False, 'error': 'Username already exists'})
        
        for user in users.values():
            if user.get('email') == email:
                return jsonify({'success': False, 'error': 'Email already registered'})
        
        users[username] = {
            'email': email,
            'password': hashlib.sha256(password.encode()).hexdigest(),
            'created_at': datetime.now().isoformat()
        }
        save_users(users)
        
        return jsonify({'success': True, 'message': 'Registration successful'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'success': False, 'error': 'Username and password are required'})
        
        users = load_users()
        
        if username not in users:
            return jsonify({'success': False, 'error': 'Invalid username or password'})
        
        user = users[username]
        if user['password'] != hashlib.sha256(password.encode()).hexdigest():
            return jsonify({'success': False, 'error': 'Invalid username or password'})
        
        session['username'] = username
        session['logged_in'] = True
        
        return jsonify({'success': True, 'message': 'Login successful', 'username': username})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logout successful'})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if 'logged_in' in session and session['logged_in']:
        username = session.get('username')
        usage = get_user_usage(username)
        return jsonify({
            'success': True,
            'logged_in': True,
            'username': username,
            'usage': usage
        })
    return jsonify({'success': True, 'logged_in': False})

@app.route('/api/upgrade_pro', methods=['POST'])
def upgrade_pro():
    try:
        # Check if user is logged in
        if 'logged_in' not in session or not session['logged_in']:
            return jsonify({'success': False, 'error': 'Bạn cần đăng nhập để nâng cấp'})
        
        username = session.get('username')
        usage = load_usage()
        
        if username not in usage:
            usage[username] = {'ban7': 0, 'spam_log': 0, 'is_pro': False}
        
        # For demo purposes, auto-upgrade to pro
        # In production, this would verify payment from telegram
        usage[username]['is_pro'] = True
        save_usage(usage)
        
        return jsonify({'success': True, 'message': 'Đã nâng cấp lên gói Pro'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
        # Check if user is logged in
        if 'logged_in' not in session or not session['logged_in']:
            return jsonify({'success': False, 'error': 'Bạn cần đăng nhập để sử dụng tính năng này'})
        
        username = session.get('username')
        usage = get_user_usage(username)
        
        # Check usage limit (1 use for free users)
        if not usage.get('is_pro', False) and usage.get('spam_log', 0) >= 1:
            return jsonify({
                'success': False,
                'error': 'Bạn đã dùng hết lượt sử dụng miễn phí. Mua gói Pro tại @minhdevtcp để dùng không giới hạn'
            })
        
        data = request.json
        access_token = data.get('access_token')
        duration = data.get('duration', '10s')  # Default 10 seconds
        action = data.get('action', 'start')  # start or stop
        
        if not access_token:
            return jsonify({'success': False, 'error': 'Access token is required'})
        
        total_seconds = parse_duration(str(duration))
        max_duration = 15 * 24 * 60 * 60  # 15 days in seconds
        if total_seconds <= 0 or total_seconds > max_duration:
            return jsonify({'success': False, 'error': f'Duration must be between 1 second and 15 days'})
        
        # For now, return a simplified response
        # In a real implementation, this would start/stop the spam log process
        if action == 'start':
            # Update usage count
            update_user_usage(username, 'spam_log')
            return jsonify({
                'success': True,
                'message': 'Spam log started',
                'duration': total_seconds,
                'status': 'running'
            })
        elif action == 'stop':
            return jsonify({
                'success': True,
                'message': 'Spam log stopped',
                'status': 'stopped'
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid action'})
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
