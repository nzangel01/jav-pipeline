import os, subprocess, json, base64, requests, re, shlex, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# FORCED CONFIG: PECORINE (.8)
TARGET_DIR = "/mnt/takao_data/JAV/esrgan_queue"
try:
    from config import VISION_OLLAMA_URL as OLLAMA_URL
except ImportError:
    OLLAMA_URL = "http://localhost:11434/api/generate"  # set in config.py
MODEL = "gemma3:4b"
LOG_FILE = "/tmp/vision_rename.log"
FRAME_TEMP = "/tmp/frames_check"
MAX_WORKERS = 2  # Reduced for stability

def log(msg):
    with open(LOG_FILE, "a") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {msg}")
        f.write(f"[{timestamp}] {msg}\n")

def get_video_duration(path):
    try:
        safe_path = shlex.quote(path)
        cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {safe_path}"
        return float(subprocess.check_output(cmd, shell=True))
    except: return 0

def extract_frames(video_path, stem):
    duration = get_video_duration(video_path)
    if duration == 0: return []
    out_dir = Path(FRAME_TEMP) / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, p in enumerate([0.1, 0.3, 0.5, 0.7, 0.9]):
        ss = duration * p
        out_file = out_dir / f"frame_{i}.jpg"
        cmd = f"ffmpeg -y -ss {ss} -i {shlex.quote(video_path)} -frames:v 1 -q:v 2 {shlex.quote(str(out_file))} > /dev/null 2>&1"
        subprocess.run(cmd, shell=True)
        if out_file.exists(): frames.append(out_file)
    return frames

def ask_vision(image_path, retries=3):
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
    payload = {"model": MODEL, "prompt": "Find JAV code watermark in this frame. Reply with code only like FC2-PPV-12345 or XXXX-123, or NONE", "images": [img_b64], "stream": False}
    
    for attempt in range(retries):
        try:
            res = requests.post(OLLAMA_URL, json=payload, timeout=90)
            text = res.json().get("response", "").strip()
            match = re.search(r'([A-Z0-9]+-[A-Z0-9-]+)', text, re.IGNORECASE)
            return match.group(1).upper() if match else "NONE"
        except Exception as e:
            if attempt == retries - 1:
                log(f"API Error after {retries} attempts: {e}")
                return "NONE"
            time.sleep(2)
    return "NONE"

def process_file(file_path):
    video_path = Path(file_path)
    stem = video_path.stem
    if re.search(r'[A-Z]{2,}-\d+', stem): return
    
    log(f"Processing: {stem}")
    frames = extract_frames(str(video_path), stem)
    if not frames: return
    
    results = [ask_vision(str(f)) for f in frames]
    results = [r for r in results if r != "NONE"]
    
    if results:
        from collections import Counter
        counts = Counter(results)
        most_common, count = counts.most_common(1)[0]
        if count >= 3:
            new_name = f"{most_common}{video_path.suffix}"
            try:
                os.rename(str(video_path), str(video_path.parent / new_name))
                log(f"SUCCESS: {stem} -> {new_name} ({count}/5)")
            except Exception as e:
                log(f"Rename Error for {stem}: {e}")
        else: log(f"Inconsistent for {stem}: {counts}")
        
    subprocess.run(f"rm -rf {shlex.quote(str(Path(FRAME_TEMP) / stem))}", shell=True)

def main():
    if not os.path.exists(FRAME_TEMP): os.makedirs(FRAME_TEMP)
    files = [os.path.join(TARGET_DIR, f) for f in os.listdir(TARGET_DIR) if f.endswith(('.mp4', '.mkv', '.ts'))]
    log(f"Start Vision Rename (Robust Mode) - {len(files)} files")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor: executor.map(process_file, files)
    log("Job Complete")

if __name__ == "__main__": main()
