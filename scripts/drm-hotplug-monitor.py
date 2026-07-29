#!/usr/bin/env python3
"""Restart the Mythe Display kiosk after a DRM connector recovers.

wlroots/Cage can keep running after an HDMI hot-unplug while its scanout no
longer has a valid output. systemd then sees a healthy process and never
applies Restart=on-failure. This monitor watches DRM connector status in
sysfs and restarts the kiosk only after an output reconnects and stays stable.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SYSFS_ROOT = Path("/sys/class/drm")
UNIT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9@_.-]+$")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def connector_statuses(sysfs_root: Path, connector: str = "") -> dict[str, str]:
    """Return DRM connector status values, optionally narrowed to one connector."""
    selected = connector.strip()
    statuses: dict[str, str] = {}
    for status_path in sorted(sysfs_root.glob("card*-*/status")):
        name = status_path.parent.name
        if selected and name != selected and not name.endswith(f"-{selected}"):
            continue
        try:
            statuses[name] = status_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return statuses


def connected_signature(statuses: dict[str, str]) -> tuple[str, ...]:
    return tuple(sorted(name for name, status in statuses.items() if status == "connected"))


@dataclass
class HotplugTracker:
    """Debounce a loss/recovery or connected-output identity change."""

    reference_signature: tuple[str, ...]
    saw_absence: bool
    candidate_signature: tuple[str, ...] = ()
    candidate_since: float = 0.0

    @classmethod
    def create(cls, signature: tuple[str, ...]) -> "HotplugTracker":
        return cls(reference_signature=signature, saw_absence=not bool(signature))

    def update(self, signature: tuple[str, ...], now: float, stable_seconds: float) -> bool:
        if not signature:
            self.saw_absence = True
            self.candidate_signature = ()
            self.candidate_since = 0.0
            return False

        if not self.saw_absence and signature == self.reference_signature:
            self.candidate_signature = ()
            self.candidate_since = 0.0
            return False

        if signature != self.candidate_signature:
            self.candidate_signature = signature
            self.candidate_since = now
            return False

        if now - self.candidate_since < stable_seconds:
            return False

        self.reference_signature = signature
        self.saw_absence = False
        self.candidate_signature = ()
        self.candidate_since = 0.0
        return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="监测 DRM connector 热插拔并恢复 Mythe Display kiosk。")
    parser.add_argument(
        "--unit",
        default=os.environ.get("MYTHE_DISPLAY_UNIT_NAME", "mythe-display-kiosk.service"),
        help="重新启动的 systemd unit。",
    )
    parser.add_argument(
        "--connector",
        default=os.environ.get("MYTHE_DISPLAY_DRM_CONNECTOR", ""),
        help="可选的 DRM connector，例如 HDMI-A-2 或 card1-HDMI-A-2。默认监测所有 connector。",
    )
    parser.add_argument(
        "--poll-ms",
        type=int,
        default=env_int("MYTHE_DISPLAY_HOTPLUG_POLL_MS", 1000),
        help="轮询 sysfs 的间隔，默认 1000ms。",
    )
    parser.add_argument(
        "--stable-ms",
        type=int,
        default=env_int("MYTHE_DISPLAY_HOTPLUG_STABLE_MS", 3500),
        help="connector reconnect 后的稳定等待时间，默认 3500ms。",
    )
    parser.add_argument("--sysfs-root", type=Path, default=DEFAULT_SYSFS_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--once", action="store_true", help="输出当前 connector 状态后退出。")
    parser.add_argument("--dry-run", action="store_true", help="检测到恢复时只输出操作，不执行 systemctl restart。")
    return parser


def restart_unit(unit: str, *, dry_run: bool) -> None:
    if not UNIT_NAME_PATTERN.fullmatch(unit):
        raise ValueError(f"无效 systemd unit 名称: {unit}")
    # The monitor is PartOf the kiosk unit. Do not wait for the restart here:
    # systemd may stop this monitor as part of the same transaction.
    command = ["systemctl", "--no-block", "restart", unit]
    if dry_run:
        print(f"[drm-hotplug] dry-run: {' '.join(command)}", flush=True)
        return
    print(f"[drm-hotplug] 已恢复 connector，执行: {' '.join(command)}", flush=True)
    subprocess.run(command, check=True, timeout=60)


def main() -> int:
    args = build_parser().parse_args()
    if not args.sysfs_root.is_dir():
        print(f"[drm-hotplug] DRM sysfs 不存在: {args.sysfs_root}", file=sys.stderr)
        return 1

    initial_statuses = connector_statuses(args.sysfs_root, args.connector)
    initial_signature = connected_signature(initial_statuses)
    print(
        f"[drm-hotplug] 监测 connector={args.connector or 'auto'}，"
        f"初始已连接={','.join(initial_signature) or 'none'}，"
        f"轮询={max(100, args.poll_ms)}ms，稳定等待={max(0, args.stable_ms)}ms",
        flush=True,
    )
    if args.once:
        return 0 if initial_statuses else 2

    tracker = HotplugTracker.create(initial_signature)
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    poll_seconds = max(0.1, args.poll_ms / 1000)
    stable_seconds = max(0.0, args.stable_ms / 1000)
    previous_signature = initial_signature
    while not stopping:
        time.sleep(poll_seconds)
        statuses = connector_statuses(args.sysfs_root, args.connector)
        signature = connected_signature(statuses)
        if signature != previous_signature:
            print(
                f"[drm-hotplug] connector 变化: "
                f"{','.join(previous_signature) or 'none'} -> {','.join(signature) or 'none'}",
                flush=True,
            )
            previous_signature = signature
        if tracker.update(signature, time.monotonic(), stable_seconds):
            try:
                restart_unit(args.unit, dry_run=args.dry_run)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                print(f"[drm-hotplug] kiosk 恢复失败: {exc}", file=sys.stderr, flush=True)
                return 1
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
