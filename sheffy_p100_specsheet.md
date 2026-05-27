# Tesla P100-PCIE-16GB — Benchmark Spec Sheet
**Tested:** 2026-04-21 | **Host:** Sheffy (192.168.1.7) | **OS:** CachyOS (Arch) | **Driver:** 580.142 / CUDA 13.0

---

## Hardware Identity
| Field | Value |
|---|---|
| Model | Tesla P100-PCIE-16GB |
| Serial Number | 0323817102238 |
| GPU UUID | GPU-887f862b-7882-be58-3e3b-9fb5e805d583 |
| Architecture | Pascal (sm_60) |
| Compute Capability | 6.0 |
| VRAM | 16,384 MB HBM2 |
| ECC | Enabled |
| TDP | 250W |
| PCIe | Gen3 x8 |
| Core Clock | 1328 MHz (SM) |
| Memory Clock | 715 MHz |

## Theoretical Performance (NVIDIA Official)
| Metric | Value |
|---|---|
| FP32 | 9.3 TFLOPS |
| FP16 | 18.7 TFLOPS |
| Memory Bandwidth | 549 GB/s (HBM2) |
| Memory Interface | 4096-bit |

## LLM Inference Benchmarks (Ollama, single GPU)
| Model | VRAM | Speed | Result |
|---|---|---|---|
| llama3:8b | ~5 GB | **50.2 t/s** | ✅ PASS |
| qwen2.5:14b | ~9 GB | **22.0 t/s** | ✅ PASS |
| qwen2.5:72b-q2_K | 29 GB | N/A — OOM | ❌ Exceeds 16GB |

> Practical limit: Models up to ~14B (Q4) หรือ ~30B (Q2) fit ใน 16GB VRAM

## Thermal Profile
| State | Temp | Power Draw |
|---|---|---|
| Cold idle | 49°C | 39 W |
| LLM inference (8b) | 51–61°C | 42–48 W |
| LLM inference (14b) | 50–55°C | 40–47 W |
| Post-load idle | 50°C | 40 W |

> Max temperature observed: **61°C** (well within 85°C limit)

## Memory Health (ECC)
| Check | Result |
|---|---|
| Single Bit Errors | **0** |
| Double Bit Errors | **0** |
| VRAM free at idle | 16,263 MB / 16,384 MB |
| Status | ✅ CLEAN |

## Compatibility
| Platform | Status |
|---|---|
| CUDA 12.x runtime | ✅ Working |
| CUDA 13.x runtime | ✅ Working (Ollama verified) |
| Docker + nvidia-container-toolkit | ✅ |
| Ollama (latest) | ✅ |
| CUDA compiler sm_60 | ⚠️ Dropped in CUDA 12.8+ (runtime fine via driver JIT) |

## Conclusion
การ์ดสภาพดี — ECC clean ไม่มี error ทั้ง single/double bit
Temperature ปกติ 50–61°C under LLM load ไม่เคย throttle
**เหมาะสำหรับ:** LLM inference server, AI/ML research, HPC
**ประสิทธิภาพ:** llama3:8b @ **50 t/s** | qwen2.5:14b @ **22 t/s**
