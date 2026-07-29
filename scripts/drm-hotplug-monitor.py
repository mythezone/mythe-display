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


def card_name_from_device(device: str) -> str:
    configured = device.strip()
    if not configured or configured == "auto":
        return ""
    return Path(configured).name


def connector_statuses(
    sysfs_root: Path,
    connector: str = "",
    device: str = "",
) -> dict[str, str]:
    """Return DRM connector status values, optionally narrowed to one connector."""
    selected = connector.strip()
    selected_card = card_name_from_device(device)
    statuses: dict[str, str] = {}
    for status_path in sorted(sysfs_root.glob("card*-*/status")):
        name = status_path.parent.name
        if selected_card and not name.startswith(f"{selected_card}-"):
            continue
        if selected and name != selected and not name.endswith(f"-{selected}"):
            continue
        try:
            statuses[name] = status_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return statuses


def connected_signature(statuses: dict[str, str]) -> tuple[str, ...]:
    return tuple(sorted(name for name, status in statuses.items() if status == "connected"))


def valid_edid(edid: bytes) -> bool:
    if len(edid) < 128:
        return False
    if edid[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return False
    # Some HDMI controller boards intermittently return a corrupt CTA
    # extension while their base EDID block and native timing remain valid.
    # Requiring every extension checksum creates a restart loop.
    return sum(edid[:128]) % 256 == 0


def connector_ready(connector_path: Path, required_mode: str = "") -> bool:
    try:
        edid = (connector_path / "edid").read_bytes()
        if not valid_edid(edid):
            return False
        if required_mode:
            modes = {
                mode.strip()
                for mode in (connector_path / "modes").read_text(encoding="utf-8").splitlines()
                if mode.strip()
            }
            if required_mode not in modes:
                return False
    except OSError:
        return False
    return True


def ready_signature(
    sysfs_root: Path,
    statuses: dict[str, str],
    required_mode: str = "",
) -> tuple[str, ...]:
    return tuple(
        sorted(
            name
            for name, status in statuses.items()
            if status == "connected" and connector_ready(sysfs_root / name, required_mode)
        )
    )


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
        "--device",
        default=os.environ.get("MYTHE_DISPLAY_DRM_DEVICE", "auto"),
        help="可选 DRM card，例如 /dev/dri/card1；auto 表示所有 card。",
    )
    parser.add_argument(
        "--mode",
        default=os.environ.get("MYTHE_DISPLAY_DRM_MODE", "3840x1100"),
        help="首选显示模式；默认只记录，不作为阻止视频输出的硬门禁。",
    )
    parser.add_argument(
        "--strict-mode",
        action="store_true",
        default=os.environ.get("MYTHE_DISPLAY_DRM_MODE_STRICT", "0") == "1",
        help="要求 EDID 必须包含 --mode；默认关闭，避免异常 EDID 导致永久黑屏。",
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
        default=env_int("MYTHE_DISPLAY_HOTPLUG_STABLE_MS", 8000),
        help="connector、EDID 和目标模式恢复后的稳定等待时间，默认 8000ms。",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=env_int("MYTHE_DISPLAY_DRM_READY_TIMEOUT_MS", 20000),
        help="--wait-ready 的最长等待时间，默认 20000ms。",
    )
    parser.add_argument("--sysfs-root", type=Path, default=DEFAULT_SYSFS_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--once", action="store_true", help="输出当前 connector 状态后退出。")
    parser.add_argument(
        "--wait-ready",
        action="store_true",
        help="等待 EDID 有效且目标模式持续稳定后退出，不监测热插拔。",
    )
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

    required_mode = args.mode if args.strict_mode else ""
    initial_statuses = connector_statuses(args.sysfs_root, args.connector, args.device)
    initial_connected = connected_signature(initial_statuses)
    initial_ready = ready_signature(args.sysfs_root, initial_statuses, required_mode)
    print(
        f"[drm-hotplug] 监测 device={args.device or 'auto'}，connector={args.connector or 'auto'}，"
        f"首选模式={args.mode or 'any'}，模式门禁={'strict' if args.strict_mode else 'fallback'}，"
        f"初始已连接={','.join(initial_connected) or 'none'}，"
        f"初始已就绪={','.join(initial_ready) or 'none'}，"
        f"轮询={max(100, args.poll_ms)}ms，稳定等待={max(0, args.stable_ms)}ms",
        flush=True,
    )
    if args.once:
        return 0 if initial_statuses else 2

    poll_seconds = max(0.1, args.poll_ms / 1000)
    stable_seconds = max(0.0, args.stable_ms / 1000)
    if args.wait_ready:
        tracker = HotplugTracker.create(())
        deadline = time.monotonic() + max(0.0, args.timeout_ms / 1000)
        while time.monotonic() <= deadline:
            statuses = connector_statuses(args.sysfs_root, args.connector, args.device)
            ready = ready_signature(args.sysfs_root, statuses, required_mode)
            if tracker.update(ready, time.monotonic(), stable_seconds):
                print(f"[drm-hotplug] DRM 输出已稳定: {','.join(ready)}", flush=True)
                return 0
            time.sleep(poll_seconds)
        print(
            f"[drm-hotplug] 等待 DRM 输出超时：没有获得有效 EDID"
            f"{f' 和模式 {args.mode}' if args.strict_mode and args.mode else ''}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    tracker = HotplugTracker.create(initial_ready)
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    previous_connected = initial_connected
    previous_ready = initial_ready
    while not stopping:
        time.sleep(poll_seconds)
        statuses = connector_statuses(args.sysfs_root, args.connector, args.device)
        connected = connected_signature(statuses)
        ready = ready_signature(args.sysfs_root, statuses, required_mode)
        if connected != previous_connected:
            print(
                f"[drm-hotplug] connector 变化: "
                f"{','.join(previous_connected) or 'none'} -> {','.join(connected) or 'none'}",
                flush=True,
            )
            previous_connected = connected
        if ready != previous_ready:
            print(
                f"[drm-hotplug] EDID/模式就绪变化: "
                f"{','.join(previous_ready) or 'none'} -> {','.join(ready) or 'none'}",
                flush=True,
            )
            previous_ready = ready
        if tracker.update(ready, time.monotonic(), stable_seconds):
            try:
                restart_unit(args.unit, dry_run=args.dry_run)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                print(f"[drm-hotplug] kiosk 恢复失败: {exc}", file=sys.stderr, flush=True)
                return 1
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
