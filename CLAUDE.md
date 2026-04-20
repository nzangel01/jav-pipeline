# JAV Pipeline Project

## Overview
ระบบ auto-process วิดีโอ JAV อัตโนมัติ:
1. **Transcode AV1** — encode ด้วย Intel Arc B580 (VAAPI)
2. **AI Upscale** — Real-ESRGAN สำหรับไฟล์ความละเอียดต่ำ
3. **Auto-Categorize** — แยก folder ตามค่ายจากชื่อไฟล์ + AI frame analysis

## Infrastructure
- **silvia (.24)** — Intel Arc B580, VAAPI AV1 encode, ESRGAN
- **Yuki (.6)** — RTX 3060 x2, ESRGAN worker
- **kurumi (.80)** — RTX 3080 Windows, ESRGAN worker หลัก
- **NFS TAKAO** — 10.10.10.240:/mnt/user/DATA mount ที่ /mnt/takao_data/

## Paths
- **Input:** /mnt/takao_data/JAV/
- **Temp:** /mnt/ai_beast/Trancoder/
- **Output:** /mnt/takao_data/JAV/complete/{studio}/
- **Unknown log:** /mnt/takao_data/JAV/complete/unknown_files.txt

## Scripts
| Script | วัตถุประสงค์ |
|---|---|
| transcode_av1.sh | Encode AV1: <1080p upscale, ≥1080p keep res |
| categorize_jav.sh | แยก folder ตามค่าย detect จากชื่อไฟล์ |
| esrgan_upscale.sh | Real-ESRGAN 4x upscale (TODO: integrate) |

## Transcode Logic
- `< 1080p` → Real-ESRGAN 4x upscale → scale 1080p → AV1 QP28
- `≥ 1080p` → AV1 QP24 ตาม resolution เดิม

## Studio Patterns (categorize_jav.sh)
FC2-PPV, COSH, UGYS, C2.Lab, NCYF, FALENO, papa日記,
Necosmo, SexSyndRome, SexFriend, yuuhui, Ladies-Collection

## Systemd Timers (silvia)
```bash
systemctl --user list-timers
# transcode.timer    — ทุก 1 ชม.
# categorize.timer   — ทุก 1 ชม.
# realesrgan.timer   — ทุก 1 ชม.
```

## Studio DB
- RAG: http://192.168.1.4:6333 collection: jav_studios
- Local: ~/jav_studios_db.json
- Unknown frames → ~/JAV_clues/ → AI identify → update categorize_jav.sh

## TODO
- [ ] Integrate Real-ESRGAN เข้า transcode pipeline
- [ ] Distributed ESRGAN: silvia + Yuki + kurumi
- [ ] AI frame identify studio อัตโนมัติ (Ollama vision)
- [ ] Web dashboard monitor pipeline status
