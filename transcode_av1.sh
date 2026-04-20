#!/bin/bash
# AV1 Transcode Script - B580 GPU (VAAPI)
# Logic:
#   < 1080p  → upscale to 1080p, AV1 QP28
#   >= 1080p → keep original resolution, AV1 QP24

SOURCE="/mnt/takao_data/JAV"
TEMP="/mnt/ai_beast/Transcoder"
OUTPUT="$SOURCE/complete"
LOG="$TEMP/transcode.log"
LOCK_FILE="$TEMP/transcode.lock"
MIN_FREE_KB=10485760  # 10GB

export LIBVA_DRIVER_NAME=iHD

command -v ffmpeg  >/dev/null || { echo "ffmpeg not found"; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe not found"; exit 1; }

mkdir -p "$TEMP" "$OUTPUT"

log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
warn() { log "WARN  $*"; }
err()  { log "ERROR $*"; }

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Already running, exit." >> "$LOG"
    exit 0
fi

log "=== AV1 Transcode Start ==="

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

    # Disk space check
    AVAIL=$(df "$TEMP" | awk 'NR==2 {print $4}')
    if [[ "$AVAIL" -lt $MIN_FREE_KB ]]; then
        err "Insufficient disk space (${AVAIL}KB free), stopping."
        rmdir "$FILE_LOCK" 2>/dev/null
        break
    fi

    HEIGHT=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=height -of csv=p=0 "$INPUT" 2>/dev/null)

    if [[ -z "$HEIGHT" || ! "$HEIGHT" =~ ^[0-9]+$ ]]; then
        warn "Cannot read video stream: $BASENAME"
        rmdir "$FILE_LOCK" 2>/dev/null
        continue
    fi

    if [[ "$HEIGHT" -lt 1080 ]]; then
        VF="scale_vaapi=w=-2:h=1080,format=vaapi"
        QP=28
        LABEL="upscale ${HEIGHT}p→1080p"
    else
        VF="format=vaapi"
        QP=24
        LABEL="keep ${HEIGHT}p"
    fi

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
        else
            err "Output file empty after encode, keeping source: $BASENAME"
            rm -f "$TMPFILE"
        fi
    else
        err "FAILED (rc=$FFMPEG_RC, ${ELAPSED}s): $BASENAME"
        rm -f "$TMPFILE"
    fi

    rmdir "$FILE_LOCK" 2>/dev/null

done < <(find "$SOURCE" -maxdepth 1 \( -name "*.ts" -o -name "*.mp4" \) -type f -print0)

log "=== Transcode Complete ==="
