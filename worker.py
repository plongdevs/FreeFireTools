#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import time
import socket
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import (
    inspect_token, do_major_login, build_login_payload, 
    aes_encrypt, parse_proto, build_login_packet_from_jwt
)

def process_spam_log_task(task):
    """Process a spam log task"""
    try:
        access_token = task['access_token']
        total_seconds = task['duration']
        task_id = task['task_id']
        
        # Step 1: Inspect token
        open_id, platform = inspect_token(access_token)
        
        # Step 2: MajorLogin
        jwt_token, key, iv = do_major_login(open_id, access_token, platform)
        
        # Step 3: GetLoginData
        enc = aes_encrypt(build_login_payload(open_id, access_token, platform))
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'X-Unity-Version': '2018.4.11f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': "OB53",
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
            'Host': 'clientbp.ggpolarbear.com',
            'Connection': 'close'
        }
        
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.post("https://clientbp.ggpolarbear.com/GetLoginData",
                             headers=headers, data=enc, verify=False, timeout=10)
        
        parsed = parse_proto(resp.content)
        online_ip = online_port = None
        
        online_addr = parsed.get(14)
        if isinstance(online_addr, list): online_addr = online_addr[0]
        if online_addr:
            if isinstance(online_addr, bytes): online_addr = online_addr.decode('utf-8', 'ignore')
            parts = online_addr.rsplit(':', 1)
            if len(parts) == 2:
                online_ip, online_port = parts[0], int(parts[1])
        
        if not online_ip:
            raise Exception('Could not find game server address')
        
        # Step 4: Build packet
        packet = build_login_packet_from_jwt(jwt_token, key, iv)
        
        # Step 5: Spam log
        start = time.time()
        count = 0
        errors = 0
        
        while time.time() - start < total_seconds:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((online_ip, int(online_port)))
                s.sendall(packet)
                count += 1
                s.close()
            except Exception as e:
                errors += 1
            time.sleep(0.5)
        
        return {
            'success': True,
            'total_sent': count,
            'errors': errors,
            'duration': total_seconds,
            'server': f'{online_ip}:{online_port}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

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

def worker_loop():
    """Main worker loop to process tasks"""
    print("🤖 Worker started - waiting for tasks...")
    
    while True:
        try:
            # Load tasks
            with open('tasks.json', 'r') as f:
                tasks = json.load(f)
            
            # Process pending tasks
            for task in tasks:
                if task.get('status') == 'pending':
                    task_id = task['task_id']
                    task_type = task.get('type')
                    
                    print(f"📋 Processing task: {task_id} ({task_type})")
                    
                    # Mark as running
                    update_task_status(task_id, 'running')
                    
                    # Process task based on type
                    if task_type == 'spam_log':
                        result = process_spam_log_task(task)
                        status = 'completed' if result.get('success') else 'failed'
                        update_task_status(task_id, status, result)
                        print(f"✅ Task {task_id} {status}: {result.get('message', result.get('error', 'N/A'))}")
                    else:
                        update_task_status(task_id, 'failed', {'error': 'Unknown task type'})
                        print(f"❌ Task {task_id} failed: Unknown task type")
            
            # Sleep before checking again
            time.sleep(5)
            
        except FileNotFoundError:
            # No tasks file yet, wait and retry
            time.sleep(5)
        except Exception as e:
            print(f"❌ Worker error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    worker_loop()
