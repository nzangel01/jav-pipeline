# jav-pipeline
JAV Pipeline: AV1 transcode + Real-ESRGAN upscale + auto-categorize

Automated video processing pipeline. Routes files through upscaling or direct transcoding based on resolution, then organizes output by studio.

## Pipeline Logic

```
Input (TS/MP4)
     |
     +-- < 1080p --> ESRGAN 4x upscale --> scale to 1080p --> AV1 QP28
     |
     +-- >= 1080p -----------------------------------------> AV1 QP24
                                                                  |
                                                        categorize_jav.sh
                                                                  |
                                                     /complete/{studio}/
```

## Scripts

| Script | Purpose |
|---|---|
| `transcode_av1.sh` | Main transcode worker — VAAPI AV1 on silvia (Arc B580), routes low-res to ESRGAN queue |
| `transcode_cpu.sh` | CPU AV1 fallback worker (Yuki TR 1950X) |
| `esrgan_worker.sh` | Linux ESRGAN worker — Real-ESRGAN 4x, lossless intermediate before final AV1 pass |
| `esrgan_worker_win.py` | Windows ESRGAN worker (kurumi RTX 3080) — receives jobs over network |
| `start_esrgan_worker.sh` | Wrapper to launch esrgan_worker.sh with correct environment |
| `categorize_jav.sh` | Sorts output into `/complete/{studio}/` by case-insensitive filename pattern match |
| `join.sh` | One-command bootstrap to register a new machine as a worker |
| `orchestrator.py` | Job queue coordinator — distributes work to transcode/ESRGAN workers |
| `dashboard.py` | Web dashboard for pipeline status monitoring |
| `ollama_monitor.py` | Monitors Ollama nodes used for vision-assisted categorization |
| `vision_rename.py` | AI frame analysis via Ollama vision to identify studio from unknown files |

### Metadata / Scraper Tools

| Script/Dir | Purpose |
|---|---|
| `jav-scraper/` | Gradio GUI + Jav321 scraper for metadata fetch |
| `javsp/` | Multi-site JAV metadata scraper (JavSP integration) |

## Infrastructure

| Machine | IP | GPU | Role |
|---|---|---|---|
| silvia | 192.168.1.24 | Intel Arc B580 | VAAPI AV1 transcode, ESRGAN (Linux) |
| Yuki | 192.168.1.6 | RTX 3060 x2 | ESRGAN worker, CPU AV1 fallback |
| kurumi | 192.168.1.80 | RTX 3080 | ESRGAN worker (Windows) |

NFS storage: TAKAO NAS at `10.10.10.240:/mnt/user/DATA` mounted at `/mnt/takao_data/`

## Paths

| Purpose | Path |
|---|---|
| Input | `/mnt/takao_data/JAV/` |
| Temp/scratch | `/mnt/ai_beast/Trancoder/` |
| Output | `/mnt/takao_data/JAV/complete/{studio}/` |
| Unknown log | `/mnt/takao_data/JAV/complete/unknown_files.txt` |

## Requirements

- **silvia**: `ffmpeg` with VAAPI, Intel Arc B580, `realesrgan-ncnn-vulkan`
- **Yuki/Linux workers**: `ffmpeg`, `realesrgan-ncnn-vulkan`, CUDA or Vulkan
- **kurumi/Windows**: Real-ESRGAN Windows binary, Python 3.x
- NFS mount to TAKAO accessible on all nodes

## Quick Start

```bash
# Start transcode worker (silvia)
./transcode_av1.sh

# Start ESRGAN worker (Linux)
./start_esrgan_worker.sh

# Join a new machine as worker
./join.sh

# Start orchestrator + dashboard
python orchestrator.py &
python dashboard.py
```

## Systemd Timers (silvia)

All three timers run hourly:

```bash
systemctl --user list-timers
# transcode.timer   — transcode_av1.sh every hour
# categorize.timer  — categorize_jav.sh every hour
# realesrgan.timer  — esrgan_worker.sh every hour
```

## Studio Patterns

`categorize_jav.sh` uses case-insensitive filename matching:

| Pattern | Studio |
|---|---|
| `FC2-PPV` | FC2 Personal Produce Video |
| `COSH` | COSH |
| `UGYS` | UGヨコハマ工房 |
| `C2.Lab` | C2.Lab |
| `NCYF` | NCYF (Neko-Clip) |
| `FALENO` | FALENO |
| `Necosmo` | Necosmo |
| `SexSyndRome` | SexSyndRome |
| `yuuhui` | yuuhui玉汇 |
| `Ladies-Collection` | Ladies Collection |
| `S-CUTE` | S-CUTE |
| `SKMJ` | SKMJ |
| `papa日記` | papa日記 |

Unknown files are logged to `unknown_files.txt` and can be identified via `vision_rename.py` using Ollama vision models.

## Recent Fixes

- Fixed `trap RETURN` bug causing lock file leaks on early exit
- ESRGAN intermediate now uses lossless encoding (`-crf 0`) to prevent quality loss before final AV1 pass
- Studio matching is case-insensitive throughout `categorize_jav.sh`
