#!/bin/bash
# AV1 Transcode Script - B580 GPU (VAAPI)
# Logic:
#   < 1080p  → route to ESRGAN queue (Yuki/kurumi upscale) → AV1 QP24
#   >= 1080p → AV1 QP24 directly

SOURCE="/mnt/takao_data/JAV"
ESRGAN_QUEUE="$SOURCE/esrgan_queue"
ESRGAN_DONE="$SOURCE/esrgan_done"
TEMP="/mnt/ai_beast/Transcoder"
OUTPUT="$SOURCE/complete"
LOG="$TEMP/transcode.log"
LOCK_FILE="$TEMP/transcode.lock"
QUEUE_LIST="$TEMP/queue.list"
DONE_LIST="$TEMP/done.list"
MIN_FREE_KB=10485760  # 10GB

export LIBVA_DRIVER_NAME=iHD

command -v ffmpeg  >/dev/null || { echo "ffmpeg not found"; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe not found"; exit 1; }

mkdir -p "$TEMP" "$OUTPUT" "$ESRGAN_QUEUE" "$ESRGAN_DONE"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
warn() { log "WARN  $*"; }
err()  { log "ERROR $*"; }

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Already running, exit." >> "$LOG"
    exit 0
fi

log "=== AV1 Transcode Start ==="

# Build queue list for this run
> "$QUEUE_LIST"
while IFS= read -r -d '' f; do
    basename "$f" >> "$QUEUE_LIST"
done < <(find "$SOURCE" -maxdepth 1 \( -name "*.ts" -o -name "*.mp4" \) -type f -print0)
QUEUE_COUNT=$(wc -l < "$QUEUE_LIST")
log "Queue: $QUEUE_COUNT file(s) found"

while IFS= read -r -d '' INPUT; do
    BASENAME=$(basename "$INPUT")
    STEM="${BASENAME%.*}"
    OUTFILE="$OUTPUT/${STEM}.mp4"
    TMPFILE="$TEMP/${STEM}.mp4"
    FILE_LOCK="$TEMP/${STEM}.lock"

    # Per-file lock to prevent race conditions between instances
    if ! mkdir "$FILE_LOCK" 2>/dev/null; then
        log "SKIP (processing): $BASENAME"
        continue
    fi
    trap "rmdir '$FILE_LOCK' 2>/dev/null" RETURN

    if [[ -f "$OUTFILE" ]]; then
        log "SKIP (exists): $BASENAME"
        rmdir "$FILE_LOCK" 2>/dev/null
        continue
    fi

    # Mark as in-progress in queue list
    sed -i "s|^${BASENAME}$|[IN_PROGRESS] ${BASENAME}|" "$QUEUE_LIST"

    # Disk space check
    AVAIL=$(df "$TEMP" | awk 'NR==2 {print $4}')
    if [[ "$AVAIL" -lt $MIN_FREE_KB ]]; then
        err "Insufficient disk space (${AVAIL}KB free), stopping."
        rmdir "$FILE_LOCK" 2>/dev/null
        break
    fi

    HEIGHT=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=height -of csv=p=0 "$INPUT" 2>/dev/null | head -1)

    if [[ -z "$HEIGHT" || ! "$HEIGHT" =~ ^[0-9]+$ ]]; then
        warn "Cannot read video stream: $BASENAME"
        rmdir "$FILE_LOCK" 2>/dev/null
        continue
    fi

    if [[ "$HEIGHT" -lt 1080 ]]; then
        # Route to ESRGAN queue for Yuki/kurumi to upscale first
        mv "$INPUT" "$ESRGAN_QUEUE/"
        log "→ESRGAN_QUEUE [${HEIGHT}p]: $BASENAME"
        sed -i "s|^\[IN_PROGRESS\] ${BASENAME}$|[ESRGAN] ${BASENAME}|" "$QUEUE_LIST"
        rmdir "$FILE_LOCK" 2>/dev/null
        continue
    fi

    VF="format=vaapi"
    QP=24
    LABEL="keep ${HEIGHT}p"

    log "START [$LABEL QP$QP]: $BASENAME"
    START_TIME=$(date +%s)

    ffmpeg -y -nostdin \
        -hwaccel vaapi \
        -hwaccel_device /dev/dri/renderD128 \
        -hwaccel_output_format vaapi \
        -i "$INPUT" \
        -vf "$VF" \
        -c:v av1_vaapi \
        -qp $QP \
        -c:a aac \
        -b:a 192k \
        -movflags +faststart \
        "$TMPFILE" 2>> "$LOG"

    FFMPEG_RC=$?
    ELAPSED=$(( $(date +%s) - START_TIME ))

    if [[ $FFMPEG_RC -eq 0 ]]; then
        OUT_SIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || echo 0)
        if [[ "$OUT_SIZE" -gt 0 ]]; then
            mv "$TMPFILE" "$OUTFILE"
            log "DONE: $BASENAME → complete/ (${ELAPSED}s)"
            rm -f "$INPUT"
            log "DELETED source: $BASENAME"
            sed -i "s|^\[IN_PROGRESS\] ${BASENAME}$|[DONE] ${BASENAME}|" "$QUEUE_LIST"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${BASENAME} (${ELAPSED}s)" >> "$DONE_LIST"
        else
            err "Output file empty after encode, keeping source: $BASENAME"
            rm -f "$TMPFILE"
            sed -i "s|^\[IN_PROGRESS\] ${BASENAME}$|[FAILED] ${BASENAME}|" "$QUEUE_LIST"
        fi
    else
        err "FAILED (rc=$FFMPEG_RC, ${ELAPSED}s): $BASENAME"
        rm -f "$TMPFILE"
        sed -i "s|^\[IN_PROGRESS\] ${BASENAME}$|[FAILED] ${BASENAME}|" "$QUEUE_LIST"
    fi

    rmdir "$FILE_LOCK" 2>/dev/null

done < <(find "$SOURCE" -maxdepth 1 \( -name "*.ts" -o -name "*.mp4" \) -type f -print0)

# Phase 2: encode ESRGAN-upscaled files (already ≥1080p, AV1 QP24)
log "--- Phase 2: ESRGAN Done Queue ---"
while IFS= read -r -d '' INPUT; do
    BASENAME=$(basename "$INPUT")
    STEM="${BASENAME%.*}"
    OUTFILE="$OUTPUT/${STEM}.mp4"
    TMPFILE="$TEMP/${STEM}.mp4"
    FILE_LOCK="$TEMP/${STEM}.lock"

    if ! mkdir "$FILE_LOCK" 2>/dev/null; then
        log "SKIP (processing): $BASENAME"
        continue
    fi

    if [[ -f "$OUTFILE" ]]; then
        log "SKIP (exists): $BASENAME"
        rmdir "$FILE_LOCK" 2>/dev/null
        continue
    fi

    log "START [esrgan→AV1 QP24]: $BASENAME"
    START_TIME=$(date +%s)

    ffmpeg -y -nostdin \
        -hwaccel vaapi \
        -hwaccel_device /dev/dri/renderD128 \
        -hwaccel_output_format vaapi \
        -i "$INPUT" \
        -vf "format=vaapi" \
        -c:v av1_vaapi \
        -qp 24 \
        -c:a aac \
        -b:a 192k \
        -movflags +faststart \
        "$TMPFILE" 2>> "$LOG"

    FFMPEG_RC=$?
    ELAPSED=$(( $(date +%s) - START_TIME ))

    if [[ $FFMPEG_RC -eq 0 ]]; then
        OUT_SIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || echo 0)
        if [[ "$OUT_SIZE" -gt 0 ]]; then
            mv "$TMPFILE" "$OUTFILE"
            log "DONE [esrgan]: $BASENAME → complete/ (${ELAPSED}s)"
            rm -f "$INPUT"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [esrgan] ${BASENAME} (${ELAPSED}s)" >> "$DONE_LIST"
        else
            err "Output empty, keeping: $BASENAME"
            rm -f "$TMPFILE"
        fi
    else
        err "FAILED esrgan encode (rc=$FFMPEG_RC): $BASENAME"
        rm -f "$TMPFILE"
    fi

    rmdir "$FILE_LOCK" 2>/dev/null

done < <(find "$ESRGAN_DONE" -maxdepth 1 -name "*.mp4" -type f -print0)

log "=== Transcode Complete ==="
