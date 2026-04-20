#!/bin/bash
# AV1 Transcode Script - B580 GPU (VAAPI)
# Logic:
#   < 1080p  → upscale to 1080p, AV1 QP28
#   >= 1080p → keep original resolution, AV1 QP24

SOURCE="/mnt/takao_data/JAV"
TEMP="/mnt/ai_beast/Trancoder"
OUTPUT="$SOURCE/complete"
LOG="$TEMP/transcode.log"

export LIBVA_DRIVER_NAME=iHD

mkdir -p "$TEMP" "$OUTPUT"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== AV1 Transcode Start ==="

while IFS= read -r -d '' INPUT; do
    BASENAME=$(basename "$INPUT")
    STEM="${BASENAME%.*}"
    OUTFILE="$OUTPUT/${STEM}.mp4"
    TMPFILE="$TEMP/${STEM}.mp4"

    if [[ -f "$OUTFILE" ]]; then
        log "SKIP (exists): $BASENAME"
        continue
    fi

    HEIGHT=$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=height -of csv=p=0 "$INPUT" 2>/dev/null)

    if [[ -z "$HEIGHT" ]]; then
        log "SKIP (no video): $BASENAME"
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

    if [[ $? -eq 0 ]]; then
        mv "$TMPFILE" "$OUTFILE"
        ELAPSED=$(( $(date +%s) - START_TIME ))
        log "DONE: $BASENAME → complete/ (${ELAPSED}s)"
        rm -f "$INPUT"
        log "DELETED source: $BASENAME"
    else
        log "FAILED: $BASENAME"
        rm -f "$TMPFILE"
    fi
done < <(find "$SOURCE" -maxdepth 1 \( -name "*.ts" -o -name "*.mp4" \) -type f -print0)

log "=== Transcode Complete ==="
