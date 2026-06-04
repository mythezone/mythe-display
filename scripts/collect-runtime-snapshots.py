#!/usr/bin/env python3
"""
Run low-frequency runtime data collectors for the kiosk static JSON endpoints.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DISK_MS = 43_200_000
DEFAULT_TELEMETRY_MS = 600_000
DEFAULT_DOCKER_MS = 600_000
DEFAULT_WEATHER_MS = 1_800_000
DEFAULT_AGENTS_MS = 300_000


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="循环生成 Mythe Display runtime JSON 快照。")
    parser.add_argument("--runtime-dir", type=Path, default=Path("public/runtime"), help="runtime JSON 输出目录。")
    parser.add_argument("--disk-ms", type=int, default=DEFAULT_DISK_MS, help="磁盘采集间隔，默认 12 小时。")
    parser.add_argument("--telemetry-ms", type=int, default=DEFAULT_TELEMETRY_MS, help="Telemetry 采集间隔，默认 10 分钟。")
    parser.add_argument("--docker-ms", type=int, default=DEFAULT_DOCKER_MS, help="Docker 采集间隔，默认 10 分钟。")
    parser.add_argument("--weather-ms", type=int, default=DEFAULT_WEATHER_MS, help="天气采集间隔，默认 30 分钟。")
    parser.add_argument("--agents-ms", type=int, default=DEFAULT_AGENTS_MS, help="Codex Agent 采集间隔，默认 5 分钟。")
    parser.add_argument("--once", action="store_true", help="只采集一次后退出。")
    parser.add_argument("--delay-first", action="store_true", help="启动后先等待一个间隔再采集，适合已执行过 --once 的后台循环。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出 JSON。")
    return parser


def run_collector(name: str, command: list[str]) -> bool:
    try:
        subprocess.run(command, cwd=ROOT_DIR, check=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[runtime] {name} 采集失败: {exc}", file=sys.stderr)
        return False


def main() -> int:
    args = build_parser().parse_args()
    pretty = ["--pretty"] if args.pretty else []
    runtime_dir = args.runtime_dir
    collectors = [
        {
            "name": "disk",
            "interval": max(60, args.disk_ms / 1000),
            "next": 0.0,
            "command": [
                sys.executable,
                str(ROOT_DIR / "scripts/collect-disk-snapshot.py"),
                "--out",
                str(runtime_dir / "disks.json"),
                "--refresh-ms",
                str(args.disk_ms),
                *pretty,
            ],
        },
        {
            "name": "telemetry",
            "interval": max(60, args.telemetry_ms / 1000),
            "next": 0.0,
            "command": [
                sys.executable,
                str(ROOT_DIR / "scripts/collect-telemetry-snapshot.py"),
                "--out",
                str(runtime_dir / "telemetry.json"),
                "--state",
                str(runtime_dir / "telemetry-state.json"),
                "--refresh-ms",
                str(args.telemetry_ms),
                *pretty,
            ],
        },
        {
            "name": "docker",
            "interval": max(60, args.docker_ms / 1000),
            "next": 0.0,
            "command": [
                sys.executable,
                str(ROOT_DIR / "scripts/collect-docker-snapshot.py"),
                "--out",
                str(runtime_dir / "docker.json"),
                "--refresh-ms",
                str(args.docker_ms),
                *pretty,
            ],
        },
        {
            "name": "weather",
            "interval": max(300, args.weather_ms / 1000),
            "next": 0.0,
            "command": [
                sys.executable,
                str(ROOT_DIR / "scripts/collect-weather-snapshot.py"),
                "--out",
                str(runtime_dir / "weather-shenzhen.json"),
                "--refresh-ms",
                str(args.weather_ms),
                *pretty,
            ],
        },
        {
            "name": "codex-agents",
            "interval": max(60, args.agents_ms / 1000),
            "next": 0.0,
            "command": [
                sys.executable,
                str(ROOT_DIR / "scripts/collect-codex-agents-snapshot.py"),
                "--out",
                str(runtime_dir / "codex-agents.json"),
                "--refresh-ms",
                str(args.agents_ms),
                *pretty,
            ],
        },
    ]
    if args.delay_first and not args.once:
        now = time.monotonic()
        for collector in collectors:
            collector["next"] = now + collector["interval"]

    while True:
        now = time.monotonic()
        had_failure = False
        for collector in collectors:
            if now >= collector["next"]:
                if not run_collector(collector["name"], collector["command"]):
                    had_failure = True
                collector["next"] = time.monotonic() + collector["interval"]
        if args.once:
            return 1 if had_failure else 0
        next_due = min(collector["next"] for collector in collectors)
        time.sleep(max(1.0, min(30.0, next_due - time.monotonic())))


if __name__ == "__main__":
    raise SystemExit(main())
