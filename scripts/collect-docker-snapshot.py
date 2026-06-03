#!/usr/bin/env python3
"""
Collect Docker container status for the kiosk Docker widget.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "public/runtime/docker.json"
DEFAULT_REFRESH_MS = 600_000


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def parse_percent(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(str(value).strip().rstrip("%"))
    except ValueError:
        return 0.0


def parse_json_lines(output: str) -> list[dict[str, Any]]:
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def normalize_state(value: str | None) -> str:
    state = str(value or "unknown").lower()
    if state.startswith("up") or state == "running":
        return "running"
    if state.startswith("exited") or state == "exited":
        return "exited"
    if "pause" in state:
        return "paused"
    if "restart" in state:
        return "restarting"
    return state


def short_memory(value: str | None) -> str:
    if not value:
        return "--"
    left = str(value).split("/")[0].strip()
    return re.sub(r"([KMGT]i?)B", r" \1B", left)


def docker_info_counts() -> tuple[int, int]:
    try:
        info = json.loads(run(["docker", "info", "--format", "{{json .}}"]).stdout)
        return int(info.get("Images") or 0), int(info.get("Volumes") or 0)
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError):
        return 0, 0


def collect(refresh_ms: int) -> dict[str, Any]:
    if not shutil.which("docker"):
        return unavailable(refresh_ms, "docker command not found")

    rows = parse_json_lines(run(["docker", "ps", "-a", "--format", "{{json .}}"]).stdout)
    stats_rows = parse_json_lines(run(["docker", "stats", "--no-stream", "--format", "{{json .}}"]).stdout)
    stats_by_name = {row.get("Name"): row for row in stats_rows}
    stats_by_id = {str(row.get("ID") or "")[:12]: row for row in stats_rows}

    containers = []
    running = 0
    stopped = 0
    cpu_total = 0.0
    memory_total = 0.0

    for row in rows:
        container_id = str(row.get("ID") or "")
        name = str(row.get("Names") or row.get("Name") or container_id[:12] or "container")
        state = normalize_state(row.get("State") or row.get("Status"))
        if state == "running":
            running += 1
        else:
            stopped += 1
        stats = stats_by_name.get(name) or stats_by_id.get(container_id[:12]) or {}
        cpu = parse_percent(stats.get("CPUPerc"))
        memory_percent = parse_percent(stats.get("MemPerc"))
        cpu_total += cpu
        memory_total += memory_percent
        containers.append(
            {
                "id": container_id[:12],
                "name": name,
                "image": row.get("Image") or "",
                "state": state,
                "status": row.get("Status") or "",
                "cpuPercent": round(cpu, 1),
                "memoryPercent": round(memory_percent, 1),
                "memory": short_memory(stats.get("MemUsage")),
            }
        )

    containers.sort(key=lambda item: (item["state"] != "running", -float(item["cpuPercent"]), item["name"]))
    images, volumes = docker_info_counts()
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": refresh_ms,
        "available": True,
        "summary": {
            "running": running,
            "stopped": stopped,
            "images": images,
            "volumes": volumes,
            "cpuPercent": round(cpu_total, 1),
            "memoryPercent": round(memory_total, 1),
        },
        "containers": containers,
    }


def unavailable(refresh_ms: int, error: str) -> dict[str, Any]:
    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": refresh_ms,
        "available": False,
        "error": error,
        "summary": {
            "running": 0,
            "stopped": 0,
            "images": 0,
            "volumes": 0,
            "cpuPercent": 0,
            "memoryPercent": 0,
        },
        "containers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Mythe Display Docker 组件 JSON 快照。")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help=f"输出路径，默认 {DEFAULT_OUTPUT}。")
    parser.add_argument("--refresh-ms", type=int, default=DEFAULT_REFRESH_MS, help="刷新周期元数据。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出。")
    args = parser.parse_args()

    try:
        payload = collect(args.refresh_ms)
    except subprocess.CalledProcessError as exc:
        payload = unavailable(args.refresh_ms, exc.stderr.strip() or str(exc))

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None) + "\n", encoding="utf-8")
    print(f"已写入 {output}: {len(payload['containers'])} containers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
