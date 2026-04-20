#!/bin/bash
# transcode_cpu.sh - Yuki (TR 1950X) CPU AV1 encode
# Runs parallel with silvia GPU encode, uses libsvtav1

SOURCE="/mnt/takao_data/JAV"
TEMP="/tmp/yuki_transcoder"
OUTPUT="$SOURCE/complete"
QUEUE="$SOURCE/esrgan_queue"
LOG="$SOURCE/transcode_cpu.log"
LOCK_DIR="$SOURCE/.locks"

mkdir -p "$TEMP" "$OUTPUT" "$QUEUE" "$LOCK_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

FS_LOCK="$SOURCE/transcode_cpu.lock"

exec 200>"$FS_LOCK"
if ! flock -n 200; then
    log "Another instance running, exiting"
    exit 0
fi

log "=== transcode_cpu Start (Yuki TR 1950X) ==="

while IFS= read -r -d '' INPUT; do
    BASENAME=$(basename "$INPUT")
    STEM="${BASENAME%.*}"
    OUTFILE="$OUTPUT/${STEM}.mp4"
    TEMPFILE="$TEMP/${STEM}_cpu.mp4"
    FILE_LOCK="$LOCK_DIR/${STEM}.lock"

    if [[ -f "$OUTFILE" ]]; then
        log "SKIP (exists): $BASENAME"
        continue
    fi

    if ! mkdir "$FILE_LOCK" 2>/dev/null; then
        log "SKIP (locked): $BASENAME"
        continue
    fi

    HEIGHT=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=height -of csv=p=0 "$INPUT" 2>/dev/null | head -1)

    if [[ -z "$HEIGHT" ]]; then
        log "SKIP (no video): $BASENAME"
        rmdir "$FILE_LOCK"
        continue
    fi

    log "CHECK [$HEIGHT p]: $BASENAME"

    if [[ "$HEIGHT" -lt 1080 ]]; then
        log "ROUTE → ESRGAN queue: $BASENAME"
        mv "$INPUT" "$QUEUE/" 2>/dev/null || log "WARN: Cannot move to queue"
        rmdir "$FILE_LOCK"
        continue
    fi

    log "ENCODE CPU AV1: $BASENAME (${HEIGHT}p)"
    START_TIME=$(date +%s)

    ffmpeg -y -nostdin -i "$INPUT" \
        -c:v libsvtav1 -preset 5 -crf 28 \
        -c:a aac -b:a 192k \
        -movflags +faststart \
        "$TEMPFILE" 2>> "$LOG"

    if [[ $? -eq 0 && -f "$TEMPFILE" ]]; then
        mv "$TEMPFILE" "$OUTFILE"
        ELAPSED=$(( $(date +%s) - START_TIME ))
        log "DONE: $BASENAME → complete/ (${ELAPSED}s)"
    else
        log "FAILED: $BASENAME"
        rm -f "$TEMPFILE"
    fi

    rmdir "$FILE_LOCK"
done < <({ find "$SOURCE" -maxdepth 1 -name "*.ts" -type f -print0; find "$SOURCE" -maxdepth 1 \( -name "*.mp4" -o -name "*.mkv" \) -type f -print0; })

log "=== transcode_cpu Complete ==="