#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import requests
import time
import sys
import os
import re
import json
import base64
import socket
import threading
from os import system
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SECRET_KEY = b"1e5898ccb8dfdd921f9bdea848768b64a201"

def decode_nickname(encoded: str) -> str:
    try:
        raw = base64.b64decode(encoded)
        dec = bytearray()
        for i, b in enumerate(raw): dec.append(b ^ SECRET_KEY[i % len(SECRET_KEY)])
        return dec.decode("utf-8", errors="replace")
    except Exception: return encoded

R  = '\033[91m'
G  = '\033[92m'
Y  = '\033[93m'
B  = '\033[94m'
P  = '\033[95m'
C  = '\033[96m'
W  = '\033[97m'
BR = '\033[1m'
RS = '\033[0m'

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])
FF_VER  = "OB53"

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
            elif wt == 1: # 64-bit
                idx += 8
            elif wt == 5: # 32-bit
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

def clear():
    system('clear' if sys.platform != 'win32' else 'cls')

def log_success(msg): print(f"{BR}{G}[✓] {RS}{G}{msg}{RS}")
def log_error(msg):   print(f"{BR}{R}[✗] {RS}{R}{msg}{RS}")
def log_info(msg):    print(f"{BR}{C}[i] {RS}{W}{msg}{RS}")
def log_warn(msg):    print(f"{BR}{Y}[!] {RS}{Y}{msg}{RS}")
def separator():      print(f"{C}{'─'*65}{RS}")

def loading(text="Processing", duration=1):
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for i in range(int(duration * 10)):
        sys.stdout.write(f"\r{BR}{Y}{text} {chars[i % len(chars)]}{RS}")
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write(f"\r{BR}{G}{text} ✓{' '*20}{RS}\n")

def convert_time(seconds):
    d, s = divmod(int(seconds), 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}d {h}h {m}m {s}s"

def parse_duration(s):
    total = 0
    parts = s.split(':')
    for part in parts:
        part = part.strip().lower()
        if not part: continue
        if part.endswith('d'): total += int(part[:-1]) * 86400
        elif part.endswith('h'): total += int(part[:-1]) * 3600
        elif part.endswith('m'): total += int(part[:-1]) * 60
        elif part.endswith('s'): total += int(part[:-1])
        elif part.isdigit(): total += int(part)
    return total

def print_header():
    clear()
    # print("Đang vào tool gộp...",'\r')
    print(f"""{BR}{C}
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ▄████  ▄▄▄       ██▀███  ▓█████  ███▄    █  ▄▄▄      ║
║  ██▒ ▀█▒▒████▄    ▓██ ▒ ██▒▓█   ▀  ██ ▀█   █ ▒████▄   ║
║ ▒██░▄▄▄░░▒▀▀██   ▓██ ░▄█ ▒▒███   ▓██  ▀█ ██▒▒██  ▀█▄ ║
║ ░▓█  ██▓░  ▄██   ▒██▀▀█▄  ▒▓█  ▄ ▓██▒  ▐▌██▒░██▄▄▄▄██║
║ ░▒▓███▀▒ ▒████▀▒ ░██▓ ▒██▒░▒████▒▒██░   ▓██░ ▓█   ▓██╝║
║                                                          ║
║          {Y}🔐 GARENA FREE FIRE TOOLS BY PLONGDEVELOPER 🔐{C}            ║
╚══════════════════════════════════════════════════════════╝{RS}
""")
def print_menu():
    print(f"""{BR}{Y}
┌──────────────────────────────────────────────────────────┐
│                      📋 MAIN MENU 📋                      │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  {G}[01]{W} Add Recovery Email      {G}[08]{W} EAT to Access Token     │
│  {G}[02]{W} Check Recovery Email    {G}[09]{W} EAT to JWT              │
│  {G}[03]{W} Check Linked Platforms  {G}[10]{W} Access to JWT           │
│  {G}[04]{W} Cancel Recovery Email   {G}[11]{W} Guest to JWT            │
│  {G}[05]{W} Unbind Email            {G}[12]{W} Spam Log               │
│  {G}[06]{W} Change Bind Email       {G}[13]{W} Long Bio                │
│  {G}[07]{W} Revoke Access Token                                         │
│  {G}[00]{W} Exit                                            │
│                                                            │
└──────────────────────────────────────────────────────────┘{RS}
""")
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
        log_error(f"Connection failed: {e}"); return None

def verify_otp(otp, email, access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
    data = {"app_id": "100067", "access_token": access_token, "otp": otp, "email": email}
    return requests.post(url, data=data, headers=GARENA_HEADERS)

def cancel_request(access_token):
    url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
    payload = {'app_id': "100067", 'access_token': access_token}
    try: requests.post(url, data=payload, headers=GARENA_HEADERS)
    except: pass

def create_bind_request(verifier_token, access_token, email):
    cancel_request(access_token)
    sec_pw = input("┌─[Đặt Security Code (6 chữ số)] ──> ").strip()
    while not sec_pw.isdigit() or len(sec_pw) != 6:
        print("Mã bảo mật phải gồm đúng 6 chữ số! Vui lòng nhập lại.")
        sec_pw = input("┌─[Đặt Security Code (6 chữ số)] ──> ").strip()
    hashed_password = hashlib.sha256(sec_pw.encode('utf-8')).hexdigest().upper()
    del sec_pw 
    url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
    data = {
        "app_id": "100067",
        "access_token": access_token,
        "verifier_token": verifier_token,
        "secondary_password": hashed_password,
        "email": email
    }
    resp = requests.post(url, data=data, headers=GARENA_HEADERS)
    return resp

def add_recovery_email():
    print_header()
    print(f"\n{BR}{P}┌─────────── ADD RECOVERY EMAIL ───────────┐{RS}\n")
    email = input(f"{C}┌─[{G}Email{C}] ──> {RS}")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    loading("Sending OTP")
    resp = send_otp(email, access_token)
    if not resp or resp.status_code != 200:
        log_error("Failed to send OTP"); return
    log_success("OTP sent!")
    otp = input(f"{C}┌─[{G}OTP{C}] ──> {RS}")
    loading("Verifying OTP")
    vr = verify_otp(otp, email, access_token)
    if vr.status_code != 200:
        log_error("OTP verification failed"); return
    verifier_token = vr.json().get("verifier_token")
    if not verifier_token:
        log_error("No verifier token"); return
    loading("Creating bind request")
    br = create_bind_request(verifier_token, access_token, email)
    if br.status_code == 200:
        log_success(f"Email {email} added successfully!")
    else:
        log_error(f"Failed: {br.text}")

def check_recovery_email():
    print_header()
    print(f"\n{BR}{P}┌─────────── CHECK RECOVERY EMAIL ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    loading("Fetching account info")
    url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
    try:
        resp = requests.get(url, params={'app_id': "100067", 'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            email = data.get("email", "")
            email_to_be = data.get("email_to_be", "")
            countdown = data.get("request_exec_countdown", 0)
            separator()
            print(f"\n{BR}{G}📧 ACCOUNT INFO:{RS}\n")
            if email == "" and email_to_be != "":
                print(f"  {Y}📨 Pending  : {C}{email_to_be}{RS}")
                print(f"  {Y}⏰ Confirm in: {C}{convert_time(countdown)}{RS}")
            elif email != "":
                print(f"  {G}✅ Email    : {C}{email}{RS}")
                print(f"  {G}🔒 Status   : {C}Verified & Active{RS}")
            else:
                print(f"  {R}⚠️  No recovery email configured{RS}")
            separator()
        else:
            log_error(f"API Error: {resp.status_code}")
    except Exception as e:
        log_error(f"Error: {e}")

def check_platforms():
    print_header()
    print(f"\n{BR}{P}┌─────────── LINKED PLATFORMS ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    loading("Scanning linked accounts")
    url = "https://100067.connect.garena.com/bind/app/platform/info/get"
    try:
        resp = requests.get(url, params={'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code not in [200, 201]:
            log_error("Failed to fetch platform data"); return
        platform_names = {3:"Facebook", 8:"Gmail", 10:"Apple", 5:"VK", 11:"Twitter (X)", 7:"Huawei"}
        data = resp.json()
        bounded = data.get("bounded_accounts", [])
        available = data.get("available_platforms", [])
        separator()
        print(f"\n{BR}{C}🔗 SECONDARY LINKED:{RS}\n")
        found = False
        for acc in bounded:
            try:
                platform = acc.get('platform')
                ui = acc.get('user_info', {})
                email = ui.get('email', '')
                nick  = ui.get('nickname', '')
                if platform in platform_names:
                    print(f"  {G}▶ {platform_names[platform]}{RS}")
                    if email: print(f"    {C}📧 {email}{RS}")
                    if nick:  print(f"    {W}📝 {nick}{RS}")
                    found = True
            except: continue
        if not found: print(f"  {Y}⚠️  No secondary links found{RS}")
        separator()
        print(f"\n{BR}{C}🎮 MAIN PLATFORM:{RS}")
        for pid, name in platform_names.items():
            if pid not in available:
                print(f"  {G}▶ {name}{RS}"); break
        separator()
    except Exception as e:
        log_error(f"Error: {e}")

def cancel_recovery_email():
    print_header()
    print(f"\n{BR}{P}┌─────────── CANCEL RECOVERY EMAIL ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    loading("Cancelling request")
    url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
    try:
        resp = requests.post(url, data={'app_id': "100067", 'access_token': access_token}, headers=GARENA_HEADERS)
        if resp.status_code == 200:
            log_success("Cancelled successfully")
            print(f"  {C}{resp.json()}{RS}")
        else:
            log_error("No active request found")
    except Exception as e:
        log_error(f"Error: {e}")

def revoke_token():
    print_header()
    print(f"\n{BR}{P}┌─────────── REVOKE ACCESS TOKEN ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    loading("Revoking token")
    try:
        resp = requests.get(f"https://100067.connect.garena.com/oauth/logout?access_token={access_token}")
        if resp.text.strip() == '{"result":0}':
            log_success("Token revoked!")
        else:
            log_error(f"Failed: {resp.text}")
    except Exception as e:
        log_error(f"Error: {e}")

def unbind_email():
    print_header()
    print(f"\n{BR}{P}┌─────────── UNBIND EMAIL ───────────┐{RS}\n")
    print(f"  {G}[1]{RS} By Email OTP")
    print(f"  {G}[2]{RS} By Secondary Password")
    choice = input(f"\n{C}┌─[{G}Option{C}] ──> {RS}")
    email = input(f"{C}┌─[{G}Linked Email{C}] ──> {RS}")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    identity_token = None
    if choice == '1':
        loading("Sending OTP")
        resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                             headers=GARENA_HEADERS,
                             data={"email": email, "locale": "en_MA", "region": "IND", "app_id": "100067", "access_token": access_token})
        if '\"result\":0' not in resp.text.replace(" ", ""):
            log_error("OTP failed"); return
        otp = input(f"{C}┌─[{G}OTP{C}] ──> {RS}")
        loading("Verifying")
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                          headers=GARENA_HEADERS,
                          data={"email": email, "otp": otp, "app_id": "100067", "access_token": access_token})
        identity_token = r.json().get("identity_token")
    elif choice == '2':
        sp = input(f"{C}┌─[{G}Security Code (6 chữ số){C}] ──> {RS}").strip()
        while not sp.isdigit() or len(sp) != 6:
            print("Mã bảo mật phải gồm đúng 6 chữ số!")
            sp = input(f"{C}┌─[{G}Security Code (6 chữ số){C}] ──> {RS}").strip()
        hashed_sp = hashlib.sha256(sp.encode('utf-8')).hexdigest().upper()
        loading("Verifying")
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                          headers=GARENA_HEADERS,
                          data={"email": email, "secondary_password": hashed_sp, "app_id": "100067", "access_token": access_token})
        identity_token = r.json().get("identity_token")
    if not identity_token:
        log_error("Failed to get identity token"); return
    loading("Creating unbind request")
    resp = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_unbind_request",
                         headers=GARENA_HEADERS,
                         data={"app_id": "100067", "access_token": access_token, "identity_token": identity_token})
    if '\"result\":0' in resp.text.replace(" ", ""):
        log_success("Unbind request created!")
    else:
        log_error(f"Failed: {resp.text}")

def change_bind_email():
    print_header()
    print(f"\n{BR}{P}┌─────────── CHANGE BIND EMAIL ───────────┐{RS}\n")
    print(f"  {G}[1]{RS} Verify Old Email by OTP")
    print(f"  {G}[2]{RS} Verify by Secondary Password")
    method = input(f"\n{C}┌─[{G}Option{C}] ──> {RS}")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}")
    old_email = input(f"{C}┌─[{G}Old Email{C}] ──> {RS}")
    new_email = input(f"{C}┌─[{G}New Email{C}] ──> {RS}")
    identity_token = None
    if method == '1':
        loading(f"Sending OTP to {old_email}")
        requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                      headers=GARENA_HEADERS,
                      data={'email': old_email, 'locale': 'en_MA', 'region': 'IND', 'app_id': '100067', 'access_token': access_token})
        otp = input(f"{C}┌─[{G}OTP for {old_email}{C}] ──> {RS}")
        loading("Verifying identity")
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                          headers=GARENA_HEADERS,
                          data={'email': old_email, 'app_id': '100067', 'access_token': access_token, 'otp': otp})
        identity_token = r.json().get("identity_token")
    elif method == '2':
        sp = input(f"{C}┌─[{G}Security Code (6 chữ số){C}] ──> {RS}").strip()
        while not sp.isdigit() or len(sp) != 6:
            print("Mã bảo mật phải gồm đúng 6 chữ số!")
            sp = input(f"{C}┌─[{G}Security Code (6 chữ số){C}] ──> {RS}").strip()
        hashed_sp = hashlib.sha256(sp.encode('utf-8')).hexdigest().upper()
        loading("Verifying")
        r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_identity",
                          headers=GARENA_HEADERS,
                          data={'email': old_email, 'secondary_password': hashed_sp, 'app_id': '100067', 'access_token': access_token})
        identity_token = r.json().get("identity_token")
    if not identity_token:
        log_error("Failed to get identity token"); return
    loading(f"Sending OTP to {new_email}")
    requests.post("https://100067.connect.garena.com/game/account_security/bind:send_otp",
                  headers=GARENA_HEADERS,
                  data={'email': new_email, 'locale': 'en_MA', 'region': 'IND', 'app_id': '100067', 'access_token': access_token})
    otp_new = input(f"{C}┌─[{G}OTP for {new_email}{C}] ──> {RS}")
    loading("Verifying new OTP")
    r = requests.post("https://100067.connect.garena.com/game/account_security/bind:verify_otp",
                      headers=GARENA_HEADERS,
                      data={'email': new_email, 'app_id': '100067', 'access_token': access_token, 'otp': otp_new})
    verifier_token = r.json().get("verifier_token")
    if not verifier_token:
        log_error("Failed to get verifier token"); return
    loading("Finalizing rebind")
    r = requests.post("https://100067.connect.garena.com/game/account_security/bind:create_rebind_request",
                      headers=GARENA_HEADERS,
                      data={'identity_token': identity_token, 'email': new_email, 'app_id': '100067',
                            'verifier_token': verifier_token, 'access_token': access_token})
    if '\"result\":0' in r.text.replace(" ", ""):
        log_success("Email rebind created!")
    else:
        log_error(f"Failed: {r.text}")


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

def feat_eat_to_access():
    print_header()
    print(f"\n{BR}{P}┌─────────── EAT to ACCESS TOKEN ───────────┐{RS}\n")
    raw = input(f"{C}┌─[{G}EAT Token / Link{C}] ──> {RS}")
    eat = extract_eat_from_input(raw)
    if not eat:
        log_error("Không tách được EAT token!"); return
    log_info(f"EAT: {eat[:20]}...")
    loading("Converting EAT to Access")
    try:
        access = eat_to_access(eat)
        if access:
            separator()
            print(f"{BR}{G}[✓] Access Token:{RS}")
            print(f"{G}{access}{RS}")
            separator()
        else:
            log_error("Không lấy được Access Token")
    except Exception as e:
        log_error(f"Lỗi: {e}")



def _varint(v):
    r = bytearray()
    while v > 0x7F:
        r.append((v & 0x7F) | 0x80); v >>= 7
    r.append(v); return bytes(r)
def _int_field(f, v):
    return _varint((f << 3) | 0) + _varint(v)

def _msg_field(f, v_bytes):
    return _varint((f << 3) | 2) + _varint(len(v_bytes)) + v_bytes

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
        'X-Unity-Version': '2018.4.11f1', 'ReleaseVersion': FF_VER,
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
    
    try:
        proto_path = os.path.join(os.getcwd(), "spam_login", "spam_login")
        if proto_path not in sys.path: sys.path.append(proto_path)
        import MajorLogin_res_pb2
        res = MajorLogin_res_pb2.MajorLoginRes()
        
        try:
            res.ParseFromString(content)
            return res.account_jwt or res.token, res.key, res.iv
        except:
            try:
                dec = aes_decrypt(content)
                res.ParseFromString(dec)
                return res.account_jwt or res.token, res.key, res.iv
            except: pass
    except: pass

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

def access_to_jwt(access_token: str):
    log_info("Inspecting token...")
    open_id, platform = inspect_token(access_token)
    log_info(f"open_id={open_id} | platform={platform}")
    for pt in [platform, 2, 3, 4, 6, 8]:
        try:
            log_info(f"Thử platform {pt}...")
            jwt, key, iv = do_major_login(open_id, access_token, pt)
            if jwt: return jwt
        except Exception as e:
            log_warn(f"Platform {pt}: {e}")
    raise Exception("Tất cả platform đều thất bại")

def feat_eat_to_jwt():
    print_header()
    print(f"\n{BR}{P}┌─────────── EAT to JWT ───────────┐{RS}\n")
    raw = input(f"{C}┌─[{G}EAT Token / Link{C}] ──> {RS}")
    eat = extract_eat_from_input(raw)
    if not eat:
        log_error("Không tách được EAT!"); return
    loading("Bước 1: EAT to Access Token")
    try:
        access = eat_to_access(eat)
        if not access:
            log_error("Không lấy được Access Token"); return
        log_success(f"Access Token OK")
        loading("Bước 2: Access to JWT")
        open_id, platform = inspect_token(access)
        jwt, _, _ = do_major_login(open_id, access, platform)
        separator()
        print(f"{BR}{G}[✓] JWT Token:{RS}")
        print(f"{G}{jwt}{RS}")
        separator()
        dec = decode_jwt(jwt)
        if dec:
            print(f"\n{Y}Decoded:{RS}")
            for k, v in dec.items():
                print(f"  {C}{k}{RS}: {W}{v}{RS}")
    except Exception as e:
        log_error(f"Lỗi: {e}")


def feat_access_to_jwt():
    print_header()
    print(f"\n{BR}{P}┌─────────── ACCESS to JWT ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}").strip()
    if not access_token:
        log_error("Access token không được trống"); return
    loading("Converting Access to JWT")
    try:
        open_id, platform = inspect_token(access_token)
        jwt, _, _ = do_major_login(open_id, access_token, platform)
        separator()
        print(f"{BR}{G}[✓] JWT Token:{RS}")
        print(f"{G}{jwt}{RS}")
        separator()
        dec = decode_jwt(jwt)
        if dec:
            print(f"\n{Y}Decoded:{RS}")
            for k, v in dec.items():
                print(f"  {C}{k}{RS}: {W}{v}{RS}")
    except Exception as e:
        log_error(f"Lỗi: {e}")


def feat_guest_to_jwt():
    print_header()
    print(f"\n{BR}{P}┌─────────── GUEST to JWT ───────────┐{RS}\n")
    uid = input(f"{C}┌─[{G}UID{C}] ──> {RS}").strip()
    pw  = input(f"{C}┌─[{G}Password{C}] ──> {RS}").strip()
    if not uid or not pw:
        log_error("UID và Password không được trống"); return
    loading("Bước 1: Guest Auth")
    try:
        open_id, access_token = guest_get_access(uid, pw)
        if not open_id or not access_token:
            log_error("Guest auth thất bại"); return
        log_success(f"Guest Auth OK")
        loading("Bước 2: MajorLogin → JWT")
        jwt, _, _ = do_major_login(open_id, access_token, 4)
        separator()
        print(f"{BR}{G}[✓] JWT Token:{RS}")
        print(f"{G}{jwt}{RS}")
        separator()
        dec = decode_jwt(jwt)
        if dec:
            print(f"\n{Y}Decoded:{RS}")
            for k, v in dec.items():
                print(f"  {C}{k}{RS}: {W}{v}{RS}")
    except Exception as e:
        log_error(f"Lỗi: {e}")


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
        log_error(f"Guest login error: {e}")
        return None, None

def feat_long_bio():
    print_header()
    print(f"\n{BR}{P}┌─────────── TIỂU SỬ DÀI ───────────┐{RS}\n")
    print(f"{C}Chọn phương thức đăng nhập:{RS}")
    print(f"  {G}[1]{W} Access Token")
    print(f"  {G}[2]{W} JWT Token")
    print(f"  {G}[3]{W} Guest (UID/Pass)")
    
    method = input(f"\n{C}┌─[{G}Lựa chọn{C}] ──> {RS}").strip()
    
    jwt_token = None
    
    if method == '1':
        at = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}").strip()
        if not at: return log_error("Token không được trống")
        loading("Đang chuyển Access to JWT")
        try:
            jwt_token = access_to_jwt(at)
            log_success("Lấy JWT thành công")
        except Exception as e: return log_error(f"Lỗi: {e}")
    elif method == '2':
        jwt_token = input(f"{C}┌─[{G}JWT Token{C}] ──> {RS}").strip()
        if not jwt_token: return log_error("JWT không được trống")
    elif method == '3':
        uid = input(f"{C}┌─[{G}UID{C}] ──> {RS}").strip()
        pw  = input(f"{C}┌─[{G}Password{C}] ──> {RS}").strip()
        if not uid or not pw: return log_error("UID/Pass không được trống")
        loading("Đang đăng nhập Guest")
        open_id, at = guest_get_access(uid, pw)
        if not open_id or not at: return log_error("Đăng nhập Guest thất bại")
        loading("Đang chuyển sang JWT")
        try:
            jwt_token, _, _ = do_major_login(open_id, at, 4)
            log_success("Lấy JWT thành công")
        except Exception as e: return log_error(f"Lỗi: {e}")
    else:
        return log_error("Lựa chọn không hợp lệ")

    bio_text = input(f"{C}┌─[{G}Nội dung Bio{C}] ──> {RS}").strip()
    if not bio_text:
        log_error("Bio không được trống"); return
    
    loading("Đang cập nhật Bio")
    try:
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
            "Expect": "100-continue", "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1",
            "ReleaseVersion": FF_VER, "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A305F Build/RP1A.200720.012)",
            "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {jwt_token}"
        }
        
        r = requests.post("https://clientbp.ggpolarbear.com/UpdateSocialBasicInfo", headers=headers, data=enc, timeout=20, verify=True)
        
        if r.status_code == 200:
            log_success("Cập nhật Bio thành công!")
        elif r.status_code == 401:
            log_error("JWT không hợp lệ hoặc hết hạn (401)")
        else:
            log_error(f"Lỗi từ server: {r.status_code}")
            
    except Exception as e:
        log_error(f"Lỗi: {e}")

def feat_spam_log():
    print_header()
    print(f"\n{BR}{P}┌─────────── SPAM LOG ───────────┐{RS}\n")
    access_token = input(f"{C}┌─[{G}Access Token{C}] ──> {RS}").strip()
    if not access_token:
        log_error("Access token không được trống"); return

    duration_str = input(f"{C}┌─[{G}Thời gian chạy (vd: 1d:2h:30m:10s){C}] ──> {RS}").strip()
    total_seconds = parse_duration(duration_str)
    if total_seconds <= 0:
        log_error("Thời gian không hợp lệ!"); return

    log_info(f"Thời gian chạy: {convert_time(total_seconds)}")
    loading("Bước 1: Inspect Token")
    try:
        open_id, platform = inspect_token(access_token)
        log_success(f"open_id={open_id} | platform={platform}")
    except Exception as e:
        log_error(f"Inspect lỗi: {e}"); return

    loading("Bước 2: MajorLogin")
    try:
        jwt_token, key, iv = do_major_login(open_id, access_token, platform)
        log_success("JWT OK")
    except Exception as e:
        log_error(f"MajorLogin lỗi: {e}"); return

    loading("Bước 3: GetLoginData")
    try:
        enc = aes_encrypt(build_login_payload(open_id, access_token, platform))
        headers = {
            'Authorization': f'Bearer {jwt_token}', 'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1', 'ReleaseVersion': FF_VER,
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
            'Host': 'clientbp.ggpolarbear.com',
            'Connection': 'close'
        }
        resp = requests.post("https://clientbp.ggpolarbear.com/GetLoginData",
                             headers=headers, data=enc, verify=False, timeout=10)
        
        parsed = parse_proto(resp.content)
        online_ip = online_port = whisper_ip = whisper_port = None
        
        online_addr = parsed.get(14)
        if isinstance(online_addr, list): online_addr = online_addr[0]
        if online_addr:
            if isinstance(online_addr, bytes): online_addr = online_addr.decode('utf-8', 'ignore')
            parts = online_addr.rsplit(':', 1)
            if len(parts) == 2:
                online_ip, online_port = parts[0], int(parts[1])
                
        whisper_addr = parsed.get(32)
        if isinstance(whisper_addr, list): whisper_addr = whisper_addr[0]
        if whisper_addr:
            if isinstance(whisper_addr, bytes): whisper_addr = whisper_addr.decode('utf-8', 'ignore')
            parts = whisper_addr.rsplit(':', 1)
            if len(parts) == 2:
                whisper_ip, whisper_port = parts[0], int(parts[1])

        if not online_ip:
            log_error("Không tìm được game server address"); return
        log_success(f"Game server: {online_ip}:{online_port}")
        if whisper_ip: log_info(f"Whisper server: {whisper_ip}:{whisper_port}")
    except Exception as e:
        log_error(f"GetLoginData lỗi: {e}"); return

    loading("Bước 4: Build packet")
    try:
        packet = build_login_packet_from_jwt(jwt_token, key, iv)
        log_success(f"Packet OK ({len(packet)} bytes)")
    except Exception as e:
        log_error(f"Build packet lỗi: {e}"); return

    separator()
    print(f"\n{BR}{G}[*] Bắt đầu Spam Log → {online_ip}:{online_port}{RS}")
    if whisper_ip: print(f"{Y}[*] Gửi whisper packet trước...{RS}")
    print(f"{Y}[*] Thời gian: {convert_time(total_seconds)} | Ctrl+C để dừng sớm{RS}\n")

    if whisper_ip and whisper_port:
        try:
            ws = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ws.settimeout(5); ws.connect((whisper_ip, int(whisper_port)))
            ws.sendall(packet); time.sleep(0.5); ws.close()
            log_success("Whisper OK")
        except: pass

    start = time.time()
    count = 0
    try:
        while time.time() - start < total_seconds:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(8)
                s.connect((online_ip, int(online_port)))
                s.sendall(packet)
                count += 1
                elapsed = time.time() - start
                remaining = total_seconds - elapsed
                try: 
                    data = s.recv(4096)
                    recv_info = f" | Recv {len(data)}B"
                except: recv_info = " | No Recv"
                print(f"\r{G}[{count}] Sent OK{recv_info} | Elapsed: {convert_time(elapsed)} | Remaining: {convert_time(remaining)}{RS}   ", end="")
                s.close()
            except Exception as e:
                count += 1
                print(f"\r{R}[{count}] Lỗi: {str(e)[:40]}{RS}   ", end="")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    print(f"\n\n{BR}{G}[✓] Xong! Tổng: {count} lần trong {convert_time(time.time()-start)}{RS}")


def main():
    while True:
        print_header()
        print_menu()
        choice = input(f"{BR}{C}┌─[{G}SELECT{C}]─> {RS}").strip()

        actions = {
            '1':  add_recovery_email,
            '01': add_recovery_email,
            '2':  check_recovery_email,
            '02': check_recovery_email,
            '3':  check_platforms,
            '03': check_platforms,
            '4':  cancel_recovery_email,
            '04': cancel_recovery_email,
            '5':  unbind_email,
            '05': unbind_email,
            '6':  change_bind_email,
            '06': change_bind_email,
            '7':  revoke_token,
            '07': revoke_token,
            '8':  feat_eat_to_access,
            '08': feat_eat_to_access,
            '9':  feat_eat_to_jwt,
            '09': feat_eat_to_jwt,
            '10': feat_access_to_jwt,
            '11': feat_guest_to_jwt,
            '12': feat_spam_log,
            '13': feat_long_bio,
        }

        if choice in ['0', '00']:
            print(f"\n{BR}{G}╔══════════════════════════════╗")
            print(f"║  {C}Tạm biệt! {G}                  ║")
            print(f"╚══════════════════════════════╝{RS}\n")
            sys.exit(0)
        elif choice in actions:
            actions[choice]()
        else:
            log_warn("Lựa chọn không hợp lệ!")

        input(f"\n{BR}{C}Nhấn Enter để tiếp tục...{RS}")

if __name__ == "__main__":
    main()
nput(f"\n{BR}{C}Nhấn Enter để tiếp tục...{RS}")

if __name__ == "__main__":
    main()
