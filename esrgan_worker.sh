#!/bin/bash
# ESRGAN Worker for JAV Pipeline
# Runs on Yuki (.6) and Kurumi (.80) via NFS shared storage

QUEUE_DIR="/mnt/takao_data/JAV/esrgan_queue"
DONE_DIR="/mnt/takao_data/JAV/esrgan_done"
LOG_FILE="$DONE_DIR/esrgan_worker.log"
LOCK_DIR="$DONE_DIR/.locks"
WORK_DIR="/tmp/esrgan_work"

BIN_YUKI="$HOME/bin/realesrgan/realesrgan-ncnn-vulkan"
BIN_KURUMI="C:\\tools\\realesrgan\\realesrgan-ncnn-vulkan"
BIN=""

FS_LOCK="$DONE_DIR/esrgan_worker.lock"
SCRIPT_LOCK="$DONE_DIR/esrgan_worker.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

mkdir -p "$QUEUE_DIR" "$DONE_DIR" "$LOCK_DIR" "$WORK_DIR"

detect_bin() {
    if [[ -x "$BIN_YUKI" ]]; then
        BIN="$BIN_YUKI"
    elif [[ -x "/usr/local/bin/realesrgan-ncnn-vulkan" ]]; then
        BIN="/usr/local/bin/realesrgan-ncnn-vulkan"
    elif command -v realesrgan-ncnn-vulkan &>/dev/null; then
        BIN=$(command -v realesrgan-ncnn-vulkan)
    else
        log "ERROR: No Real-ESRGAN binary found"
        exit 1
    fi
    log "Using binary: $BIN"
}

flock_check() {
    exec 200>"$FS_LOCK"
    if ! flock -n 200; then
        log "Another instance is running, exiting"
        exit 0
    fi
    echo $$ > "$SCRIPT_LOCK"
}

cleanup() {
    rm -rf "$WORK_DIR"/*
    rm -f "$SCRIPT_LOCK"
}

trap cleanup EXIT

process_file() {
    local INPUT="$1"
    local BASENAME=$(basename "$INPUT")
    local STEM="${BASENAME%.*}"
    
    local FILE_LOCK="$LOCK_DIR/${STEM}.lock"
    local OUTPUT="$DONE_DIR/${STEM}_esrgan.mp4"
    local TEMP_FRAMES="$WORK_DIR/frames"
    local TEMP_UPSCALED="$WORK_DIR/upscaled"
    local TEMP_OUTPUT="$WORK_DIR/output.mp4"
    
    mkdir -p "$TEMP_FRAMES" "$TEMP_UPSCALED"
    
    log "START: $BASENAME"
    local START_TIME=$(date +%s)
    
    if [[ -f "$OUTPUT" ]]; then
        log "SKIP (exists): $BASENAME"
        rmdir "$FILE_LOCK"
        return 0
    fi
    
    # Detect source framerate
    local FPS
    FPS=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=r_frame_rate -of csv=p=0 "$INPUT" 2>/dev/null | head -1)
    FPS=$(echo "scale=3; $FPS" | bc 2>/dev/null || echo "30")

    log "Extracting frames from $BASENAME (fps=$FPS)"
    ffmpeg -y -i "$INPUT" "$TEMP_FRAMES/frame_%04d.png" 2>> "$LOG_FILE"
    if [[ $? -ne 0 ]]; then
        log "ERROR: Failed to extract frames from $BASENAME"
        rm -rf "$TEMP_FRAMES" "$TEMP_UPSCALED"
        rmdir "$FILE_LOCK"
        return 1
    fi

    FRAME_COUNT=$(ls -1 "$TEMP_FRAMES"/*.png 2>/dev/null | wc -l)
    log "Upscaling $FRAME_COUNT frames (4x) via folder mode"

    local UPSCALE_START=$(date +%s)
    "$BIN" -i "$TEMP_FRAMES" -o "$TEMP_UPSCALED" -n realesrgan-x4plus -s 4 2>> "$LOG_FILE"
    local UPSCALE_END=$(date +%s)
    local UPSCALE_TIME=$((UPSCALE_END - UPSCALE_START))
    log "Upscaled $FRAME_COUNT frames in ${UPSCALE_TIME}s"

    log "Reassembling video with audio"
    ffmpeg -y -framerate "$FPS" -i "$TEMP_UPSCALED/frame_%04d.png" \
        -i "$INPUT" \
        -map 0:v -map 1:a? \
        -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
        -c:a copy \
        "$TEMP_OUTPUT" 2>> "$LOG_FILE"
    
    if [[ $? -eq 0 && -f "$TEMP_OUTPUT" ]]; then
        mv "$TEMP_OUTPUT" "$OUTPUT"
        local END_TIME=$(date +%s)
        local ELAPSED=$((END_TIME - START_TIME))
        log "DONE: $BASENAME → ${STEM}_esrgan.mp4 (${ELAPSED}s)"
    else
        log "ERROR: Failed to reassemble video from $BASENAME"
    fi
    
    rm -rf "$TEMP_FRAMES" "$TEMP_UPSCALED"
    rmdir "$FILE_LOCK"
    
    return 0
}

main() {
    detect_bin
    flock_check
    
    log "=== ESRGAN Worker Started ==="
    log "Queue: $QUEUE_DIR"
    log "Done: $DONE_DIR"
    
    while true; do
        while IFS= read -r -d '' INPUT; do
            local BASENAME=$(basename "$INPUT")
            local STEM="${BASENAME%.*}"
            local FILE_LOCK="$LOCK_DIR/${STEM}.lock"
            
            if mkdir "$FILE_LOCK" 2>/dev/null; then
                process_file "$INPUT"
            else
                log "SKIP (locked by another worker): $BASENAME"
            fi
        done < <(find "$QUEUE_DIR" -maxdepth 1 \( -name "*.mp4" -o -name "*.ts" -o -name "*.mkv" \) -type f -print0 2>/dev/null)
        
        sleep 30
    done
}

main "$@"
