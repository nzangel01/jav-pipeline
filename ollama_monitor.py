#!/usr/bin/env python3
import json, time, urllib.request, subprocess, os
from datetime import datetime

try:
    from config import OLLAMA_NODES as NODES
except ImportError:
    NODES = {}  # copy config.example.py → config.py and fill in your IPs

OUT = '/tmp/ollama_fleet_status.json'
ALERT_LOG = '/tmp/ollama_alerts.log'
INTERVAL = 60
VRAM_ZOMBIE_THRESHOLD_GB = 1.0  # VRAM used but no model loaded = zombie

def log_alert(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] ALERT: {msg}"
    print(line)
    with open(ALERT_LOG, 'a') as f:
        f.write(line + '\n')

def check_node(name, info):
    base = info['url']
    try:
        req = urllib.request.urlopen(f'{base}/api/ps', timeout=2)
        data = json.loads(req.read())
        models = data.get('models', [])
        total_vram = sum(m.get('size_vram', 0) for m in models)

        # zombie detection: Ollama responds but no model loaded yet VRAM high
        # (can't check nvidia-smi remotely easily, but flag if ps shows no model)
        alert = None
        if not models:
            alert = None  # normal idle

        return {
            'status': 'online',
            'models': [
                {'name': m.get('name','?'),
                 'size_gb': round(m.get('size', 0)/1e9, 1),
                 'vram_gb': round(m.get('size_vram', 0)/1e9, 1),
                 'state': 'busy' if m.get('expires_at') else 'idle'}
                for m in models
            ],
            'alert': alert
        }
    except Exception:
        return {'status': 'offline', 'models': [], 'alert': None}

def auto_heal(name, info):
    """restart ollama via SSH if node is offline"""
    ssh = info.get('ssh')
    if not ssh:
        return
    try:
        result = subprocess.run(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=3',
             ssh, 'systemctl restart ollama 2>/dev/null || docker restart ollama 2>/dev/null'],
            capture_output=True, timeout=10
        )
        log_alert(f"{name} auto-heal: restart ollama (exit {result.returncode})")
    except Exception as e:
        log_alert(f"{name} auto-heal failed: {e}")

prev_status = {}

while True:
    result = {'updated': datetime.now().isoformat(), 'nodes': {}}
    for name, info in NODES.items():
        node = check_node(name, info)
        result['nodes'][name] = node

        # alert on status change offline → was online
        was_online = prev_status.get(name) == 'online'
        if node['status'] == 'offline' and was_online:
            log_alert(f"{name} went OFFLINE — attempting auto-heal")
            auto_heal(name, info)

        prev_status[name] = node['status']

    with open(OUT, 'w') as f:
        json.dump(result, f, indent=2)

    time.sleep(INTERVAL)
