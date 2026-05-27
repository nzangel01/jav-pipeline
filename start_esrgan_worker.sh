#!/bin/bash
# Deploy and start ESRGAN worker on remote machines
# Requires SSH key auth: ssh-copy-id nzangel@<host>

SCRIPT_DIR="$HOME/jav-pipeline"
REMOTE_SCRIPT="$SCRIPT_DIR/esrgan_worker.sh"

YUKI="${YUKI_HOST:-nzangel@yuki}"
KURUMI="${KURUMI_HOST:-nzangel@kurumi}"

echo "=== Deploying ESRGAN Worker ==="
echo "Targets: $YUKI, $KURUMI"
echo "Override with YUKI_HOST= and KURUMI_HOST= env vars"
echo ""

echo "[1/4] Copying script to Yuki..."
ssh "$YUKI" "mkdir -p $SCRIPT_DIR"
scp "$REMOTE_SCRIPT" "$YUKI:$REMOTE_SCRIPT"
ssh "$YUKI" "chmod +x $REMOTE_SCRIPT"

echo "[2/4] Creating queue/done folders on NFS..."
ssh "$YUKI" "mkdir -p /mnt/takao_data/JAV/esrgan_queue /mnt/takao_data/JAV/esrgan_done"

echo "[3/4] Copying script to Kurumi (Windows)..."
ssh "$KURUMI" "cmd /c mkdir C:\\tools\\jav-pipeline 2>nul; exit 0"
scp "$REMOTE_SCRIPT" "$KURUMI:C:/tools/jav-pipeline/esrgan_worker.sh"

echo "[4/4] Creating queue/done folders on Kurumi..."
ssh "$KURUMI" "cmd /c mkdir C:\\takao_data\\JAV\\esrgan_queue C:\\takao_data\\JAV\\esrgan_done 2>nul; exit 0"

echo ""
echo "=== To start workers manually ==="
echo "  Yuki:   ssh $YUKI 'nohup ~/jav-pipeline/esrgan_worker.sh > /dev/null 2>&1 &'"
echo "  Kurumi: ssh $KURUMI 'cmd /c start C:\\tools\\jav-pipeline\\esrgan_worker.sh'"
echo ""
echo "=== To check status ==="
echo "  Yuki:   ssh $YUKI 'tail -f /mnt/takao_data/JAV/esrgan_done/esrgan_worker.log'"
