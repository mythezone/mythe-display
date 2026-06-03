#!/usr/bin/env python3
"""
Collect low-frequency CPU, memory, and network telemetry for the kiosk widget.
"""

from __future__ import annotations

import argparse
import json
import math
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
    rx_rate = max(0.0, (current_network["rx"] - int(previous_network.get("rx", 0))) / elapsed)
    tx_rate = max(0.0, (current_network["tx"] - int(previous_network.get("tx", 0))) / elapsed)
    network_percent = min(100.0, ((rx_rate + tx_rate) / NETWORK_SCALE_BYTES_PER_SEC) * 100.0)

    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append(
        {
            "ts": now,
            "cpu": rounded(cpu),
            "memory": rounded(memory),
            "network": rounded(network_percent),
        }
    )
    history = history[-history_limit:]

    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": refresh_ms,
        "series": {
            "cpu": [row["cpu"] for row in history],
            "memory": [row["memory"] for row in history],
            "network": [row["network"] for row in history],
        },
        "metrics": {
            "cpuPercent": rounded(cpu),
            "memoryPercent": rounded(memory),
            "networkPercent": rounded(network_percent),
            "networkRx": format_rate(rx_rate),
            "networkTx": format_rate(tx_rate),
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

    print(f"已写入 {args.out}: CPU {payload['metrics']['cpuPercent']}%, Memory {payload['metrics']['memoryPercent']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
