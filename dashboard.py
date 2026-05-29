#!/usr/bin/env python3
from flask import Flask, render_template_string
import os
import re
import subprocess
import json
from datetime import datetime
import urllib.request

app = Flask(__name__)

LOG_PATHS = {
    'Yuki CPU': '/mnt/takao_data/JAV/transcode_cpu.log',
    'Silvia AV1': '/mnt/ai_beast/Transcoder/transcode.log',
    'Yuki ESRGAN': '/mnt/takao_data/JAV/esrgan_done/esrgan_worker.log',
}

QUEUE_PATHS = {
    'pending': '/mnt/takao_data/JAV/',
    'esrgan_queue': '/mnt/takao_data/JAV/esrgan_queue/',
    'esrgan_done': '/mnt/takao_data/JAV/esrgan_done/',
    'complete': '/mnt/takao_data/JAV/complete/',
}

TEMP_PATHS = {
    'Silvia AV1': '/mnt/ai_beast/Transcoder/',
    'Yuki ESRGAN': '/var/lib/docker/esrgan_work',
}

FLEET_DIR = '/mnt/takao_data/JAV/fleet/'

try:
    from config import OLLAMA_DASHBOARD_NODES as OLLAMA_NODES
except ImportError:
    OLLAMA_NODES = {}  # copy config.example.py → config.py and fill in your IPs

LAST_TEMP_FILE = '/tmp/dashboard_temp_state.json'

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>JAV Pipeline Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: monospace; margin: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #e94560; }
        table { border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #444; padding: 8px 12px; text-align: left; }
        th { background: #16213e; color: #e94560; }
        tr:nth-child(even) { background: #1f1f3a; }
        .done { color: #4ecca3; }
        .failed { color: #e94560; }
        .running { color: #f9a826; }
        .pending { color: #aaa; }
        .stale { color: #ff6b6b; }
        .section { margin: 30px 0; }
    </style>
</head>
<body>
    <h1>JAV Pipeline Dashboard</h1>
    <p>Last updated: {{ now }}</p>

    <div class="section">
        <h2>Per-Worker Status</h2>
        <table>
            <tr><th>Worker</th><th>Jobs Sent</th><th>Jobs Done</th><th>Failed</th><th>Running</th></tr>
            {% for w, d in workers.items() %}
            <tr>
                <td>{{ w }}</td>
                <td>{{ d.sent }}</td>
                <td class="done">{{ d.done }}</td>
                <td class="failed">{{ d.failed }}</td>
                <td class="running">{{ d.running }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Queue Status</h2>
        <table>
            <tr><th>Queue</th><th>Count</th></tr>
            {% for q, c in queues.items() %}
            <tr><td>{{ q }}</td><td>{{ c }}</td></tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Temp Disk Space</h2>
        <table>
            <tr><th>Worker</th><th>Temp Path</th><th>Used</th><th>Free</th><th>Total</th><th>Status</th></tr>
            {% for w, t in temps.items() %}
            <tr>
                <td>{{ w }}</td>
                <td>{{ t.path }}</td>
                <td>{{ t.used }}</td>
                <td>{{ t.free }}</td>
                <td>{{ t.total }}</td>
                <td class="{{ t.status }}">{{ t.status }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Fleet Registry</h2>
        <table>
            <tr><th>Hostname</th><th>IP</th><th>GPU</th><th>CPU</th><th>Type</th><th>OS</th><th>Joined</th></tr>
            {% for w in fleet %}
            <tr>
                <td>{{ w.get('hostname','?') }}</td>
                <td>{{ w.get('ip','?') }}</td>
                <td>{{ w.get('gpu','none') }}</td>
                <td>{{ w.get('cpu_cores','?') }}</td>
                <td class="done">{{ w.get('worker_type','?') }}</td>
                <td>{{ w.get('os','?')[:30] }}</td>
                <td>{{ w.get('joined_at','?')[:16] }}</td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="pending">No workers registered (fleet dir empty)</td></tr>
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Ollama Fleet</h2>
        <table>
            <tr><th>Node</th><th>Status</th><th>Model</th><th>Size</th><th>VRAM</th><th>State</th></tr>
            {% for node, info in ollama.items() %}
            {% if info.models %}
            {% for m in info.models %}
            <tr>
                <td>{{ node }}</td>
                <td class="done">online</td>
                <td>{{ m.name }}</td>
                <td>{{ m.size }}</td>
                <td>{{ m.vram }}</td>
                <td class="{{ 'running' if m.state == 'busy' else 'pending' }}">{{ m.state }}</td>
            </tr>
            {% endfor %}
            {% else %}
            <tr>
                <td>{{ node }}</td>
                <td class="{{ 'failed' if info.status == 'offline' else 'pending' }}">{{ info.status }}</td>
                <td colspan="4" class="pending">{{ 'no model loaded' if info.status == 'online' else '—' }}</td>
            </tr>
            {% endif %}
            {% endfor %}
        </table>
    </div>

    <div class="section">
        <h2>Recent Jobs Timeline</h2>
        <table>
            <tr><th>Worker</th><th>Job</th><th>Time</th><th>Status</th></tr>
            {% for j in timeline %}
            <tr>
                <td>{{ j.worker }}</td>
                <td>{{ j.job }}</td>
                <td>{{ j.time }}</td>
                <td class="{{ j.status }}">{{ j.status }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>
'''

def get_ollama_status():
    nodes = {}
    for name, base in OLLAMA_NODES.items():
        try:
            req = urllib.request.urlopen(f'{base}/api/ps', timeout=2)
            data = json.loads(req.read())
            models = data.get('models', [])
            nodes[name] = {'status': 'online', 'models': [
                {'name': m.get('name','?'), 'size': f"{m.get('size',0)/1e9:.1f}GB",
                 'vram': f"{m.get('size_vram',0)/1e9:.1f}GB",
                 'state': 'busy' if m.get('expires_at') else 'idle'}
                for m in models
            ]}
        except Exception:
            nodes[name] = {'status': 'offline', 'models': []}
    return nodes

def count_files(path):
    if not os.path.exists(path):
        return 0
    try:
        if os.path.isdir(path):
            return len([f for f in os.listdir(path) if not f.startswith('.')])
        return 1
    except:
        return 0

def parse_log(log_path):
    stats = {'sent': 0, 'done': 0, 'failed': 0, 'running': 0, 'jobs': []}
    if not os.path.exists(log_path):
        return stats
    try:
        with open(log_path, 'r', errors='ignore') as f:
            content = f.read()
        stats['sent'] = content.count('Start')
        stats['done'] = content.count('Complete')
        stats['failed'] = content.count('Error') + content.count('FAILED')
        stats['running'] = content.count(' running') + content.count(' encoding')
    except Exception as e:
        stats['error'] = str(e)
    return stats

def get_disk_usage(path):
    try:
        if path.startswith('/mnt/') or path.startswith('/tmp/'):
            result = subprocess.run(['df', '-BG', path], capture_output=True, text=True, timeout=10)
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                parts = lines[1].split()
                total = parts[1]
                used = parts[2]
                free = parts[3]
                return {'used': used, 'free': free, 'total': total}
    except Exception as e:
        return {'used': 'N/A', 'free': 'N/A', 'total': 'N/A', 'error': str(e)}
    return {'used': 'N/A', 'free': 'N/A', 'total': 'N/A'}

def get_temp_usage(worker, path):
    result = {'path': path, 'used': 'N/A', 'free': 'N/A', 'total': 'N/A', 'status': 'N/A'}
    try:
        if worker == 'Kurumi' and path.endswith('.json'):
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                result['path'] = data.get('temp_path', 'C:\\temp\\esrgan_work')
                return result
        elif path.startswith('/'):
            du = get_disk_usage(path)
            result.update(du)
            
            last_state = load_last_temp_state()
            if last_state and worker in last_state:
                last_used = last_state[worker].get('used')
                curr_used = du.get('used')
                if last_used and curr_used and last_used != curr_used:
                    if last_used > curr_used:
                        result['status'] = 'OK (reclaimed)'
                    else:
                        result['status'] = 'stale temp ⚠️'
                else:
                    result['status'] = 'OK'
            else:
                result['status'] = 'OK'
    except Exception as e:
        result['status'] = f'error: {e}'
    return result

def load_last_temp_state():
    try:
        if os.path.exists(LAST_TEMP_FILE):
            with open(LAST_TEMP_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return None

def save_temp_state(temps):
    try:
        state = {w: {'used': t.get('used'), 'free': t.get('free')} for w, t in temps.items()}
        with open(LAST_TEMP_FILE, 'w') as f:
            json.dump(state, f)
    except:
        pass

def load_fleet():
    workers = []
    if not os.path.isdir(FLEET_DIR):
        return workers
    import glob
    for jf in glob.glob(FLEET_DIR + '*.json'):
        try:
            with open(jf) as f:
                workers.append(json.load(f))
        except Exception:
            pass
    return workers

def get_timeline():
    timeline = []
    for worker, path in LOG_PATHS.items():
        if os.path.exists(path):
            try:
                with open(path, 'r', errors='ignore') as f:
                    lines = f.readlines()[-100:]
                for line in lines:
                    if 'Complete' in line or 'Start' in line or 'Error' in line:
                        m = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
                        if m:
                            status = 'complete' if 'Complete' in line else ('failed' if 'Error' in line else 'running')
                            job_match = re.search(r'([^\s]+(?:\.mp4|\.ts))', line)
                            job = job_match.group(1)[:30] if job_match else worker
                            timeline.append({'worker': worker, 'job': job, 'time': m.group(1), 'status': status})
            except:
                pass
    timeline.sort(key=lambda x: x['time'], reverse=True)
    return timeline[:20]

@app.route('/')
def index():
    workers = {w: parse_log(p) for w, p in LOG_PATHS.items()}
    queues = {q: count_files(p) for q, p in QUEUE_PATHS.items()}
    temps = {w: get_temp_usage(w, p) for w, p in TEMP_PATHS.items()}
    save_temp_state(temps)
    timeline = get_timeline()
    fleet = load_fleet()
    ollama = get_ollama_status()
    return render_template_string(HTML, workers=workers, queues=queues, temps=temps, timeline=timeline, fleet=fleet, ollama=ollama, now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7788, debug=False)