#!/usr/bin/env python3
"""
JAV Pipeline Orchestrator — openai-agents on Kokkoro (Qwen3-Coder:30b)
scanner agent → dispatcher agent
"""
import asyncio
import subprocess
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled

set_tracing_disabled(True)

try:
    from config import OLLAMA_URL
except ImportError:
    OLLAMA_URL = "http://localhost:11434/v1"  # set in config.py
MODEL = "qwen3-coder:30b"
NFS = "/mnt/takao_data/JAV"

client = AsyncOpenAI(base_url=OLLAMA_URL, api_key="ollama")

def model():
    return OpenAIChatCompletionsModel(model=MODEL, openai_client=client)


def scan_queue() -> str:
    """Scan JAV NFS queue and return status report."""
    lines = []
    import os, pathlib

    base = pathlib.Path(NFS)
    if not base.exists():
        return "ERROR: NFS not mounted"

    def count(path, exts):
        p = pathlib.Path(path)
        if not p.exists():
            return 0
        return sum(1 for f in p.iterdir() if f.suffix.lower() in exts)

    video_exts = {".ts", ".mp4", ".mkv"}
    pending   = count(NFS, video_exts)
    esrgan_q  = count(f"{NFS}/esrgan_queue", video_exts)
    esrgan_done = count(f"{NFS}/esrgan_done", video_exts)
    complete  = count(f"{NFS}/complete", {".mp4"})

    # check locks (active encodes)
    locks = count(f"{NFS}/.locks", {".lock"}) if pathlib.Path(f"{NFS}/.locks").exists() else 0
    lock_dirs = [d.name for d in pathlib.Path(f"{NFS}/.locks").iterdir()] if pathlib.Path(f"{NFS}/.locks").exists() else []

    lines.append(f"Pending transcode : {pending} files")
    lines.append(f"ESRGAN queue      : {esrgan_q} files (need upscale)")
    lines.append(f"ESRGAN done       : {esrgan_done} files (ready for AV1)")
    lines.append(f"Complete          : {complete} files")
    lines.append(f"Active locks      : {locks}")
    if lock_dirs:
        lines.append(f"  Processing      : {', '.join(lock_dirs[:5])}")

    # check systemd timers
    result = subprocess.run(
        ["systemctl", "--user", "list-timers", "--no-pager", "--no-legend"],
        capture_output=True, text=True
    )
    active_timers = [l.split()[-1] for l in result.stdout.strip().splitlines() if "jav" in l.lower()]
    lines.append(f"Active timers     : {', '.join(active_timers) if active_timers else 'none'}")

    return "\n".join(lines)


async def main():
    status = scan_queue()
    print("=== Queue Scan ===")
    print(status)
    print()

    scanner = Agent(
        name="scanner",
        instructions=(
            "You analyze JAV pipeline queue status data. "
            "Report key numbers clearly and flag any issues like stalled queues or missing workers."
        ),
        model=model(),
    )

    dispatcher = Agent(
        name="dispatcher",
        instructions=(
            "You are a pipeline dispatcher. Given a queue status report, "
            "decide the optimal action: which worker should run next, "
            "whether to rebalance, and what to prioritize. "
            "Be specific and concise. Output in Thai."
        ),
        model=model(),
    )

    print("=== Scanner Agent ===")
    r1 = await Runner.run(scanner, f"Pipeline status:\n{status}\n\nAnalyze this.")
    print(r1.final_output)
    print()

    print("=== Dispatcher Agent ===")
    r2 = await Runner.run(dispatcher, r1.final_output)
    print(r2.final_output)


if __name__ == "__main__":
    asyncio.run(main())
