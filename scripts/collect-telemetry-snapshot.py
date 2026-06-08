#!/usr/bin/env python3
"""
Collect low-frequency CPU, memory, and network telemetry for the kiosk widget.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "public/runtime/telemetry.json"
DEFAULT_STATE = "public/runtime/telemetry-state.json"
DEFAULT_REFRESH_MS = 600_000
DEFAULT_HISTORY_LIMIT = 18
NETWORK_SCALE_BYTES_PER_SEC = 125_000_000


def read_cpu() -> dict[str, int]:
    with Path("/proc/stat").open("r", encoding="utf-8") as handle:
        parts = handle.readline().split()
    values = [int(value) for value in parts[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return {"idle": idle, "total": total}


def cpu_percent(previous: dict[str, int], current: dict[str, int]) -> float:
    total_delta = current["total"] - previous["total"]
    idle_delta = current["idle"] - previous["idle"]
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))


def read_memory_percent() -> float:
    values: dict[str, int] = {}
    with Path("/proc/meminfo").open("r", encoding="utf-8") as handle:
        for line in handle:
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (1.0 - available / total) * 100.0))


def read_float_file(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_nvidia_gpu() -> dict[str, Any] | None:
    if not shutil.which("nvidia-smi"):
        return None
    command = [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    gpus: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5:
            continue
        name, raw_util, raw_temp, raw_mem_used, raw_mem_total = parts[:5]
        try:
            util = float(raw_util)
            temp = float(raw_temp)
            mem_used = float(raw_mem_used)
            mem_total = float(raw_mem_total)
        except ValueError:
            continue
        gpus.append(
            {
                "name": name or "NVIDIA GPU",
                "percent": max(0.0, min(100.0, util)),
                "temperatureC": temp,
                "memoryUsedMiB": mem_used,
                "memoryTotalMiB": mem_total,
                "memoryPercent": max(0.0, min(100.0, (mem_used / mem_total) * 100.0)) if mem_total > 0 else 0.0,
            }
        )

    if not gpus:
        return None
    busiest = max(gpus, key=lambda item: item["percent"])
    busiest["available"] = True
    busiest["source"] = "nvidia-smi"
    busiest["count"] = len(gpus)
    return busiest


def read_sysfs_gpu() -> dict[str, Any] | None:
    candidates = sorted(Path(path) for path in glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"))
    for busy_path in candidates:
        busy = read_float_file(busy_path)
        if busy is None:
            continue
        device_dir = busy_path.parent
        label = device_dir.parent.name.replace("card", "GPU ")
        temp = None
        for temp_path in sorted(device_dir.glob("hwmon/hwmon*/temp*_input")):
            raw_temp = read_float_file(temp_path)
            if raw_temp is not None:
                temp = raw_temp / 1000.0
                break
        return {
            "available": True,
            "source": "sysfs",
            "name": label,
            "percent": max(0.0, min(100.0, busy)),
            "temperatureC": temp,
        }
    return None


def read_gpu() -> dict[str, Any]:
    return read_nvidia_gpu() or read_sysfs_gpu() or {"available": False, "source": "unavailable", "percent": 0.0}


def include_interface(name: str) -> bool:
    excluded_prefixes = ("lo", "docker", "br-", "veth", "virbr", "zt", "tailscale")
    return not name.startswith(excluded_prefixes)


def read_network_bytes() -> dict[str, int]:
    rx = 0
    tx = 0
    fallback_rx = 0
    fallback_tx = 0
    with Path("/proc/net/dev").open("r", encoding="utf-8") as handle:
        for line in handle.readlines()[2:]:
            if ":" not in line:
                continue
            name, values = line.split(":", 1)
            iface = name.strip()
            fields = values.split()
            if len(fields) < 16 or iface == "lo":
                continue
            iface_rx = int(fields[0])
            iface_tx = int(fields[8])
            fallback_rx += iface_rx
            fallback_tx += iface_tx
            if include_interface(iface):
                rx += iface_rx
                tx += iface_tx
    return {"rx": rx or fallback_rx, "tx": tx or fallback_tx}


def format_rate(bytes_per_second: float) -> str:
    units = ["B/s", "KB/s", "MB/s", "GB/s"]
    value = max(0.0, bytes_per_second)
    index = 0
    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1
    return f"{value:.0f} {units[index]}" if value >= 10 or index == 0 else f"{value:.1f} {units[index]}"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def rounded(value: float) -> int:
    if not math.isfinite(value):
        return 0
    return int(round(max(0.0, min(100.0, value))))


def read_uptime_seconds() -> float:
    value = read_text_file(Path("/proc/uptime")).split()
    if not value:
        return 0.0
    try:
        return max(0.0, float(value[0]))
    except ValueError:
        return 0.0


def read_load() -> dict[str, float]:
    parts = read_text_file(Path("/proc/loadavg")).split()
    values: list[float] = []
    for raw in parts[:3]:
        try:
            values.append(float(raw))
        except ValueError:
            values.append(0.0)
    while len(values) < 3:
        values.append(0.0)
    return {"one": values[0], "five": values[1], "fifteen": values[2]}


def read_temperatures(gpu: dict[str, Any]) -> list[dict[str, Any]]:
    readings: list[dict[str, Any]] = []
    for hwmon_dir in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        chip = read_text_file(hwmon_dir / "name") or hwmon_dir.name
        for input_path in sorted(hwmon_dir.glob("temp*_input")):
            raw = read_float_file(input_path)
            if raw is None:
                continue
            celsius = raw / 1000.0
            if celsius < -40 or celsius > 130:
                continue
            suffix = input_path.name.removeprefix("temp").removesuffix("_input")
            label = read_text_file(hwmon_dir / f"temp{suffix}_label")
            readings.append(
                {
                    "label": f"{chip} {label}".strip() if label else chip,
                    "celsius": round(celsius, 1),
                }
            )
    gpu_temp = gpu.get("temperatureC")
    if gpu.get("available") and isinstance(gpu_temp, (int, float)) and math.isfinite(gpu_temp):
        readings.append({"label": gpu.get("name") or "GPU", "celsius": round(float(gpu_temp), 1)})
    readings.sort(key=lambda row: float(row.get("celsius") or 0), reverse=True)
    return readings[:8]


def format_duration(seconds: float) -> str:
    total_minutes = int(max(0, seconds) // 60)
    days, remainder = divmod(total_minutes, 1440)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def collect(state_path: Path, refresh_ms: int, history_limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_state(state_path)
    now = time.time()
    previous_cpu = state.get("cpu")
    previous_network = state.get("network")
    previous_ts = float(state.get("ts") or 0)

    if not previous_cpu:
        previous_cpu = read_cpu()
        time.sleep(0.25)
    current_cpu = read_cpu()

    if not previous_network:
        previous_network = read_network_bytes()
        previous_ts = now
        time.sleep(0.1)
        now = time.time()
    current_network = read_network_bytes()

    elapsed = max(0.1, now - previous_ts)
    cpu = cpu_percent(previous_cpu, current_cpu)
    memory = read_memory_percent()
    gpu = read_gpu()
    rx_rate = max(0.0, (current_network["rx"] - int(previous_network.get("rx", 0))) / elapsed)
    tx_rate = max(0.0, (current_network["tx"] - int(previous_network.get("tx", 0))) / elapsed)
    network_percent = min(100.0, ((rx_rate + tx_rate) / NETWORK_SCALE_BYTES_PER_SEC) * 100.0)
    gpu_percent = float(gpu.get("percent") or 0.0) if gpu.get("available") else 0.0

    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append(
        {
            "ts": now,
            "cpu": rounded(cpu),
            "memory": rounded(memory),
            "gpu": rounded(gpu_percent),
            "network": rounded(network_percent),
        }
    )
    history = history[-history_limit:]
    temperatures = read_temperatures(gpu)
    hottest = temperatures[0] if temperatures else {}

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": refresh_ms,
        "series": {
            "cpu": [row["cpu"] for row in history],
            "memory": [row["memory"] for row in history],
            "gpu": [row.get("gpu", 0) for row in history],
            "network": [row["network"] for row in history],
        },
        "metrics": {
            "cpuPercent": rounded(cpu),
            "memoryPercent": rounded(memory),
            "gpuAvailable": bool(gpu.get("available")),
            "gpuPercent": rounded(gpu_percent) if gpu.get("available") else None,
            "gpuName": gpu.get("name") or "",
            "gpuTemperatureC": round(float(gpu["temperatureC"]), 1)
            if isinstance(gpu.get("temperatureC"), (int, float)) and math.isfinite(float(gpu["temperatureC"]))
            else None,
            "gpuMemoryUsedMiB": round(float(gpu["memoryUsedMiB"]), 1)
            if isinstance(gpu.get("memoryUsedMiB"), (int, float))
            else None,
            "gpuMemoryTotalMiB": round(float(gpu["memoryTotalMiB"]), 1)
            if isinstance(gpu.get("memoryTotalMiB"), (int, float))
            else None,
            "gpuMemoryPercent": rounded(float(gpu["memoryPercent"]))
            if isinstance(gpu.get("memoryPercent"), (int, float))
            else None,
            "networkPercent": rounded(network_percent),
            "networkRx": format_rate(rx_rate),
            "networkTx": format_rate(tx_rate),
        },
        "health": {
            "uptimeSeconds": round(read_uptime_seconds()),
            "uptime": format_duration(read_uptime_seconds()),
            "load": read_load(),
            "temperatures": temperatures,
            "maxTemperatureC": hottest.get("celsius"),
            "maxTemperatureLabel": hottest.get("label", ""),
        },
    }
    next_state = {
        "ts": now,
        "cpu": current_cpu,
        "network": current_network,
        "history": history,
    }
    return payload, next_state


def write_json(path: Path, payload: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Mythe Display Telemetry JSON 快照。")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help=f"输出路径，默认 {DEFAULT_OUTPUT}。")
    parser.add_argument("--state", default=DEFAULT_STATE, help=f"状态路径，默认 {DEFAULT_STATE}。")
    parser.add_argument("--refresh-ms", type=int, default=DEFAULT_REFRESH_MS, help="刷新周期元数据。")
    parser.add_argument("--history-limit", type=int, default=DEFAULT_HISTORY_LIMIT, help="保留采样点数量。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出。")
    args = parser.parse_args()

    try:
        payload, state = collect(Path(args.state), args.refresh_ms, max(2, args.history_limit))
        write_json(Path(args.out), payload, args.pretty)
        write_json(Path(args.state), state, args.pretty)
    except OSError as exc:
        print(f"采集 Telemetry 失败: {exc}", file=sys.stderr)
        return 1

    gpu_text = (
        f", GPU {payload['metrics']['gpuPercent']}%"
        if payload["metrics"].get("gpuAvailable")
        else ", GPU unavailable"
    )
    print(f"已写入 {args.out}: CPU {payload['metrics']['cpuPercent']}%, Memory {payload['metrics']['memoryPercent']}%{gpu_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
