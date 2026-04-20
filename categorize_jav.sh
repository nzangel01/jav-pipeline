#!/bin/bash
# JAV Auto-Categorizer
# - ตรวจชื่อไฟล์ → แยก folder ตามค่าย
# - ชื่อ hash / unknown → Unsorted/ + บันทึกใน unknown_files.txt

TARGET="/mnt/takao_data/JAV/complete"
UNSORTED="$TARGET/Unsorted"
UNKNOWN_LOG="$TARGET/unknown_files.txt"

mkdir -p "$UNSORTED"

# Pattern → folder name (เพิ่มค่ายได้เรื่อยๆ)
declare -A STUDIOS=(
    ["FC2-PPV"]="FC2-PPV"
    ["FC2PPV"]="FC2-PPV"
    ["COSH"]="COSH"
    ["UGYS"]="UGYS"
    ["C2.Lab"]="C2.Lab"
    ["C2Lab"]="C2.Lab"
    ["NCYF"]="NCYF"
    ["papa日記"]="FC2-PPV"
    ["FALENO"]="FALENO"
    ["fone"]="FALENO"
    ["Necosmo"]="Necosmo"
    ["SexSyndRome"]="SexSyndRome"
    ["SexFriend"]="SexFriend"
    ["yuuhui"]="yuuhui"
    ["Ladies.Collection"]="Ladies-Collection"
    ["Ladies_Collection"]="Ladies-Collection"
)

moved=0
unknown=0

while IFS= read -r -d '' FILE; do
    BASENAME=$(basename "$FILE")
    MATCHED=""

    for pattern in "${!STUDIOS[@]}"; do
        if [[ "$BASENAME" == *"$pattern"* ]]; then
            MATCHED="${STUDIOS[$pattern]}"
            break
        fi
    done

    if [[ -n "$MATCHED" ]]; then
        DEST="$TARGET/$MATCHED"
        mkdir -p "$DEST"
        mv "$FILE" "$DEST/"
        echo "[SORTED] $BASENAME → $MATCHED/"
        ((moved++))
    else
        # ตรวจว่าเป็น hash name หรือไม่ (ไม่มีช่องว่าง, ยาว >10, alphanumeric)
        STEM="${BASENAME%.*}"
        if [[ "$STEM" =~ ^[A-Za-z0-9_\-]{10,}$ ]] && [[ ! "$STEM" =~ [[:space:]] ]]; then
            mv "$FILE" "$UNSORTED/"
            echo "[HASH→Unsorted] $BASENAME" | tee -a "$UNKNOWN_LOG"
        else
            # ชื่อยาว/ภาษาอื่น → log ไว้ให้ tool อื่นระบุ
            echo "$BASENAME" >> "$UNKNOWN_LOG"
            echo "[UNKNOWN→log] $BASENAME"
        fi
        ((unknown++))
    fi

done < <(find "$TARGET" -maxdepth 1 -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.ts" \) -print0)

echo ""
echo "=== Done: $moved sorted | $unknown unknown ==="
echo "Unknown log: $UNKNOWN_LOG"
