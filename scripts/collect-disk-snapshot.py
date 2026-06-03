#!/usr/bin/env python3
"""
Collect a compact disk usage snapshot for the kiosk storage widget.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "public/runtime/disks.json"


def run_json(command: list[str]) -> Any:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def parse_df() -> dict[str, dict[str, Any]]:
    output = run_text(["df", "-B1", "--output=source,size,used,pcent,target"])
    rows: dict[str, dict[str, Any]] = {}
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        source, size, used, percent, target = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            rows[target] = {
                "source": source,
                "totalBytes": int(size),
                "usedBytes": int(used),
                "usedPercent": int(percent.rstrip("%")),
            }
        except ValueError:
            continue
    return rows


def walk_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for device in devices:
        flat.append(device)
        flat.extend(walk_devices(device.get("children") or []))
    return flat


def first_mountpoint(device: dict[str, Any]) -> str | None:
    mountpoints = device.get("mountpoints") or []
    for mountpoint in mountpoints:
        if mountpoint:
            return str(mountpoint)
    for child in device.get("children") or []:
        mountpoint = first_mountpoint(child)
        if mountpoint:
            return mountpoint
    return None


def classify_device(device: dict[str, Any]) -> str:
    name = str(device.get("name") or "")
    path = str(device.get("path") or "")
    transport = str(device.get("tran") or "").lower()
    rota = device.get("rota")
    if transport == "usb":
        return "usb"
    if name.startswith("nvme") or "/nvme" in path:
        return "nvme"
    if rota in (False, 0, "0"):
        return "ssd"
    return "hdd"


def status_for(percent: int | None) -> str:
    if percent is None:
        return "unknown"
    if percent >= 90:
        return "bad"
    if percent >= 78:
        return "warn"
    return "ok"


def collect() -> dict[str, Any]:
    lsblk = run_json(
        [
            "lsblk",
            "-J",
            "-b",
            "-o",
            "NAME,PATH,TYPE,SIZE,TRAN,ROTA,MOUNTPOINTS,MODEL,SERIAL",
        ]
    )
    df = parse_df()
    disks = []
    total_bytes = 0
    used_bytes = 0

    for device in lsblk.get("blockdevices", []):
        if device.get("type") != "disk":
            continue
        mountpoint = first_mountpoint(device)
        usage = df.get(mountpoint or "")
        total = int(device.get("size") or 0)
        used = usage["usedBytes"] if usage else 0
        percent = usage["usedPercent"] if usage else None
        disk_type = classify_device(device)
        total_bytes += total
        used_bytes += used
        disks.append(
            {
                "id": str(device.get("name") or device.get("path")),
                "name": str(device.get("name") or device.get("path")),
                "type": disk_type,
                "role": "mounted" if mountpoint else "unmounted",
                "mount": mountpoint,
                "model": str(device.get("model") or "").strip(),
                "usedPercent": percent if percent is not None else 0,
                "totalBytes": total,
                "usedBytes": used,
                "status": status_for(percent),
            }
        )

    return {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "refreshMs": 3600000,
        "summary": {
            "totalBytes": total_bytes,
            "usedBytes": used_bytes,
            "diskCount": len(disks),
        },
        "disks": disks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Mythe Display 磁盘组件 JSON 快照。")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help=f"输出路径，默认 {DEFAULT_OUTPUT}。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出。")
    args = parser.parse_args()

    try:
        payload = collect()
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"采集磁盘信息失败: {exc}", file=sys.stderr)
        return 1

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    print(f"已写入 {output}: {payload['summary']['diskCount']} disks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
