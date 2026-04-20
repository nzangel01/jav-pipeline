#!/bin/bash
# join.sh — jav-pipeline worker bootstrap
# Copy to any Linux machine, run once to join the fleet automatically

REPO_URL="https://github.com/nzangel01/jav-pipeline"
PIPELINE_DIR="$HOME/jav-pipeline"
NFS_HOST="10.10.10.240"
NFS_EXPORT="/mnt/user/DATA"
NFS_MOUNT="/mnt/takao_data"
FLEET_DIR="$NFS_MOUNT/JAV/fleet"

log()  { echo "[join] $*"; }
err()  { echo "[join] ERROR: $*" >&2; exit 1; }
ok()   { echo "[join] ✓ $*"; }

# 1. OS check — Windows not supported by this script
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Windows detected — use join.bat / esrgan_worker_win.py instead"
    exit 0
fi

log "=== jav-pipeline worker bootstrap ==="
log "Host: $(hostname) | $(date)"

# 2. Detect capabilities
WORKER_TYPE="transcode_cpu"
GPU_NAME="none"
CPU_CORES=$(nproc)

# NVIDIA check — prefer for ESRGAN (Vulkan/CUDA)
if command -v nvidia-smi &>/dev/null && nvidia-smi --query-gpu=name --format=csv,noheader &>/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | sed 's/^ *//')
    WORKER_TYPE="esrgan"
    ok "NVIDIA GPU: $GPU_NAME → esrgan worker"
# Intel Arc / VAAPI check — for AV1 hw encode
elif command -v vainfo &>/dev/null && vainfo 2>/dev/null | grep -qE 'VAProfileH264|VAProfileHEVC|VAProfileAV1'; then
    GPU_NAME=$(vainfo 2>/dev/null | grep -i 'driver version\|DRI\|Intel' | head -1 | sed 's/^ *//' || echo "VAAPI GPU")
    WORKER_TYPE="transcode_av1"
    ok "VAAPI GPU: $GPU_NAME → AV1 transcode worker"
# Fallback: CPU only
else
    ok "No GPU detected (CPU cores: $CPU_CORES) → CPU transcode worker"
fi

# 3. NFS mount
log "Checking NFS $NFS_HOST:$NFS_EXPORT → $NFS_MOUNT ..."
if mountpoint -q "$NFS_MOUNT" 2>/dev/null; then
    ok "NFS already mounted"
else
    sudo mkdir -p "$NFS_MOUNT"
    if sudo mount -t nfs -o rw,hard,intr,timeo=14,nfsvers=3 "$NFS_HOST:$NFS_EXPORT" "$NFS_MOUNT"; then
        ok "NFS mounted"
        # Persist in fstab
        if ! grep -qs "$NFS_HOST:$NFS_EXPORT" /etc/fstab; then
            echo "$NFS_HOST:$NFS_EXPORT $NFS_MOUNT nfs rw,hard,intr,timeo=14,nfsvers=3 0 0" | sudo tee -a /etc/fstab > /dev/null
            log "Added to /etc/fstab"
        fi
    else
        err "NFS mount failed — check 10G network and NFS server"
    fi
fi

# 4. git clone / pull
log "Syncing jav-pipeline repo..."
if [[ -d "$PIPELINE_DIR/.git" ]]; then
    git -C "$PIPELINE_DIR" pull --ff-only 2>/dev/null && ok "git pull done" || log "git pull skipped (local changes or no internet)"
else
    git clone "$REPO_URL" "$PIPELINE_DIR" && ok "git clone done" || err "git clone failed — check network"
fi
chmod +x "$PIPELINE_DIR"/*.sh 2>/dev/null || true

# 5. Install missing deps
log "Checking deps..."
MISSING=()
command -v ffmpeg &>/dev/null       || MISSING+=(ffmpeg)
command -v git    &>/dev/null       || MISSING+=(git)
command -v nfs-common &>/dev/null   || dpkg -l nfs-common &>/dev/null 2>&1 || MISSING+=(nfs-common)

# Check SVT-AV1 encoder available in ffmpeg
if command -v ffmpeg &>/dev/null && ! ffmpeg -hide_banner -encoders 2>/dev/null | grep -q 'svt_av1\|libsvtav1'; then
    MISSING+=(libsvtav1-enc-dev)
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
    log "Installing: ${MISSING[*]}"
    sudo apt-get update -qq && sudo apt-get install -y "${MISSING[@]}" \
        && ok "deps installed" \
        || log "WARNING: some deps failed — may need manual install"
else
    ok "all deps present"
fi

# 6. Setup systemd user timer
log "Setting up systemd user timer ($WORKER_TYPE, every 1h)..."
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

case "$WORKER_TYPE" in
    esrgan)        SVC="jav-esrgan";        SCRIPT="$PIPELINE_DIR/esrgan_worker.sh" ;;
    transcode_av1) SVC="jav-transcode-av1"; SCRIPT="$PIPELINE_DIR/transcode_av1.sh" ;;
    transcode_cpu) SVC="jav-transcode-cpu"; SCRIPT="$PIPELINE_DIR/transcode_cpu.sh" ;;
esac
LOGFILE="$PIPELINE_DIR/${SVC}.log"

cat > "$SYSTEMD_DIR/${SVC}.service" << EOF
[Unit]
Description=JAV Pipeline Worker: $WORKER_TYPE
After=network.target

[Service]
Type=oneshot
ExecStart=$SCRIPT
StandardOutput=append:$LOGFILE
StandardError=append:$LOGFILE
EOF

cat > "$SYSTEMD_DIR/${SVC}.timer" << EOF
[Unit]
Description=JAV Pipeline Worker Timer: $WORKER_TYPE

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${SVC}.timer" && ok "timer ${SVC}.timer enabled"

# 7. Register in fleet
log "Registering in fleet registry..."
mkdir -p "$FLEET_DIR"
HOSTNAME_VAL=$(hostname)
IP_VAL=$(hostname -I 2>/dev/null | awk '{print $1}')
OS_VAL=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || uname -s)
JOINED_AT=$(date -Iseconds)

cat > "$FLEET_DIR/${HOSTNAME_VAL}.json" << EOF
{
  "hostname": "$HOSTNAME_VAL",
  "ip": "$IP_VAL",
  "gpu": "$GPU_NAME",
  "cpu_cores": $CPU_CORES,
  "os": "$OS_VAL",
  "worker_type": "$WORKER_TYPE",
  "script": "$SCRIPT",
  "timer": "${SVC}.timer",
  "joined_at": "$JOINED_AT"
}
EOF
ok "Registered: $FLEET_DIR/${HOSTNAME_VAL}.json"

# 8. Summary
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    jav-pipeline worker joined! ✓         ║"
echo "╠══════════════════════════════════════════╣"
printf "║  Host   : %-30s║\n" "$HOSTNAME_VAL ($IP_VAL)"
printf "║  OS     : %-30s║\n" "$OS_VAL"
printf "║  GPU    : %-30s║\n" "$GPU_NAME"
printf "║  Cores  : %-30s║\n" "${CPU_CORES} cores"
printf "║  Type   : %-30s║\n" "$WORKER_TYPE"
printf "║  Timer  : %-30s║\n" "${SVC}.timer (1h)"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Logs  : $LOGFILE"
echo "  Fleet : $FLEET_DIR/${HOSTNAME_VAL}.json"
echo ""
echo "  Run now: systemctl --user start ${SVC}.service"
