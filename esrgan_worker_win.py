#!/usr/bin/env python3
"""ESRGAN Worker for Windows (Kurumi .80) - RTX 3080"""

import os
import sys
import time
import subprocess
import shutil
import socket
from pathlib import Path
from datetime import datetime

QUEUE_DIR = Path(r"Z:\JAV\esrgan_queue")
DONE_DIR  = Path(r"Z:\JAV\esrgan_done")
LOCK_DIR  = DONE_DIR / ".locks"
LOG_FILE  = DONE_DIR / "esrgan_worker.log"
TEMP_BASE = Path(r"C:\temp\esrgan_work")

HOSTNAME = socket.gethostname()

REALESRGAN_CANDIDATES = [
    Path(r"C:\tools\realesrgan\realesrgan-ncnn-vulkan.exe"),
    Path(r"C:\realesrgan\realesrgan-ncnn-vulkan.exe"),
]


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{HOSTNAME}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def detect_bin():
    for p in REALESRGAN_CANDIDATES:
        if p.exists():
            return str(p)
    result = subprocess.run(["where", "realesrgan-ncnn-vulkan.exe"],
                            capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().splitlines()[0]
    return None


def get_framerate(video_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate",
             "-of", "csv=p=0", str(video_path)],
            capture_output=True, text=True
        )
        raw = result.stdout.strip().splitlines()[0]
        if "/" in raw:
            num, den = raw.split("/")
            return round(int(num) / int(den), 3)
        return float(raw)
    except Exception:
        return 30.0


def acquire_lock(lock_path):
    try:
        lock_path.mkdir(exist_ok=False)
        return True
    except FileExistsError:
        return False
    except Exception as e:
        log(f"Lock error: {e}")
        return False


def release_lock(lock_path):
    try:
        lock_path.rmdir()
    except Exception:
        pass


def process_file(input_path, binary):
    stem = input_path.stem
    file_lock = LOCK_DIR / f"{stem}.lock"
    output = DONE_DIR / f"{stem}_esrgan.mp4"

    if output.exists():
        log(f"SKIP (exists): {input_path.name}")
        release_lock(file_lock)
        return

    log(f"START: {input_path.name}")
    start_time = time.time()

    temp_dir    = TEMP_BASE / stem
    frames_dir  = temp_dir / "frames"
    upscaled_dir = temp_dir / "upscaled"
    temp_out    = temp_dir / "output.mp4"

    try:
        frames_dir.mkdir(parents=True, exist_ok=True)
        upscaled_dir.mkdir(parents=True, exist_ok=True)

        # Extract frames
        log(f"Extracting frames...")
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path),
             str(frames_dir / "frame_%04d.png")],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            log(f"ERROR extract frames: {input_path.name}")
            return

        frame_count = len(list(frames_dir.glob("*.png")))
        log(f"Upscaling {frame_count} frames (folder mode 4x)")

        # Upscale via folder mode
        upscale_start = time.time()
        r = subprocess.run(
            [binary, "-i", str(frames_dir), "-o", str(upscaled_dir),
             "-n", "realesrgan-x4plus", "-s", "4"],
            capture_output=True
        )
        upscale_time = time.time() - upscale_start
        log(f"Upscaled {frame_count} frames in {upscale_time:.1f}s")

        # Reassemble with audio from original
        fps = get_framerate(input_path)
        log(f"Reassembling at {fps}fps with audio")
        r = subprocess.run(
            ["ffmpeg", "-y",
             "-framerate", str(fps),
             "-i", str(upscaled_dir / "frame_%04d.png"),
             "-i", str(input_path),
             "-map", "0:v", "-map", "1:a?",
             "-c:v", "h264_nvenc", "-preset", "p4",
             "-cq", "18", "-pix_fmt", "yuv420p",
             "-c:a", "copy",
             str(temp_out)],
            capture_output=True, text=True
        )

        if r.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 0:
            shutil.move(str(temp_out), str(output))
            elapsed = time.time() - start_time
            log(f"DONE: {input_path.name} ({elapsed:.1f}s)")
            input_path.unlink(missing_ok=True)
        else:
            log(f"ERROR reassemble: {input_path.name}")

    except Exception as e:
        log(f"ERROR: {e}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        release_lock(file_lock)


def main():
    for d in [QUEUE_DIR, DONE_DIR, LOCK_DIR, TEMP_BASE]:
        d.mkdir(parents=True, exist_ok=True)

    binary = detect_bin()
    if not binary:
        log("ERROR: realesrgan-ncnn-vulkan.exe not found")
        sys.exit(1)

    log(f"=== ESRGAN Worker Started ===")
    log(f"Binary: {binary}")
    log(f"Queue: {QUEUE_DIR}")

    while True:
        try:
            for ext in ["*.mp4", "*.ts", "*.mkv"]:
                for input_path in sorted(QUEUE_DIR.glob(ext)):
                    stem = input_path.stem
                    file_lock = LOCK_DIR / f"{stem}.lock"
                    if acquire_lock(file_lock):
                        process_file(input_path, binary)
                    else:
                        log(f"SKIP (locked): {input_path.name}")
        except Exception as e:
            log(f"Loop error: {e}")

        time.sleep(30)


if __name__ == "__main__":
    main()
