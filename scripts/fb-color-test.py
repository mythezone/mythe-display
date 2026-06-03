#!/usr/bin/env python3
"""Minimal Linux framebuffer color test for a headless display host."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path


DRM_ROOT = Path("/sys/class/drm")
FB_ROOT = Path("/sys/class/graphics")

NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "yellow": (255, 255, 0),
}


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except PermissionError:
        return "<permission denied>"


def parse_size(value: str | None) -> tuple[int, int]:
    if not value:
        raise RuntimeError("无法读取 framebuffer virtual_size")
    match = re.fullmatch(r"\s*(\d+),(\d+)\s*", value)
    if not match:
        raise RuntimeError(f"无法解析 framebuffer virtual_size: {value!r}")
    return int(match.group(1)), int(match.group(2))


def parse_color(value: str) -> tuple[int, int, int]:
    normalized = value.strip().lower()
    if normalized in NAMED_COLORS:
        return NAMED_COLORS[normalized]
    if normalized.startswith("#"):
        normalized = normalized[1:]
    if not re.fullmatch(r"[0-9a-f]{6}", normalized):
        raise argparse.ArgumentTypeError("颜色必须是 #RRGGBB 或 black/red/green/blue 等名称")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def pixel_for_bpp(rgb: tuple[int, int, int], bpp: int) -> bytes:
    red, green, blue = rgb
    if bpp == 32:
        return bytes((blue, green, red, 0x00))
    if bpp == 24:
        return bytes((blue, green, red))
    if bpp == 16:
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        return value.to_bytes(2, byteorder="little")
    raise RuntimeError(f"暂不支持 {bpp}bpp framebuffer")


def framebuffer_sysfs(device: str) -> Path:
    name = Path(device).name
    path = FB_ROOT / name
    if not path.exists():
        raise RuntimeError(f"找不到 {path}")
    return path


def framebuffer_info(device: str) -> dict[str, object]:
    path = framebuffer_sysfs(device)
    width, height = parse_size(read_text(path / "virtual_size"))
    bpp_text = read_text(path / "bits_per_pixel")
    stride_text = read_text(path / "stride")
    if not bpp_text:
        raise RuntimeError("无法读取 framebuffer bits_per_pixel")
    bpp = int(bpp_text)
    stride = int(stride_text) if stride_text else width * (bpp // 8)
    return {
        "device": device,
        "name": read_text(path / "name"),
        "width": width,
        "height": height,
        "bitsPerPixel": bpp,
        "stride": stride,
        "writable": os.access(device, os.W_OK),
    }


def drm_connectors() -> list[dict[str, object]]:
    connectors: list[dict[str, object]] = []
    for connector in sorted(DRM_ROOT.glob("card*-*")):
        status_path = connector / "status"
        if not status_path.exists():
            continue
        modes_text = read_text(connector / "modes") or ""
        connectors.append(
            {
                "name": connector.name,
                "status": read_text(status_path),
                "enabled": read_text(connector / "enabled"),
                "dpms": read_text(connector / "dpms"),
                "modes": [line for line in modes_text.splitlines() if line],
            }
        )
    return connectors


def print_info(device: str) -> None:
    payload = {
        "framebuffer": framebuffer_info(device),
        "drmConnectors": drm_connectors(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def fill_rows(
    device: str,
    rows: list[bytes],
    duration: float | None,
    restore: bool,
) -> None:
    info = framebuffer_info(device)
    width = int(info["width"])
    height = int(info["height"])
    stride = int(info["stride"])
    bpp = int(info["bitsPerPixel"])
    bytes_per_pixel = bpp // 8
    visible_row_bytes = width * bytes_per_pixel
    total_bytes = stride * height

    if any(len(row) != stride for row in rows):
        raise RuntimeError("内部错误：row 长度必须等于 framebuffer stride")

    backup = None
    with open(device, "r+b", buffering=0) as framebuffer:
        if restore:
            backup = framebuffer.read(total_bytes)
            framebuffer.seek(0)

        for y in range(height):
            row = rows[y % len(rows)]
            framebuffer.write(row)

        framebuffer.flush()

        if duration is not None:
            time.sleep(duration)
            if restore and backup is not None:
                framebuffer.seek(0)
                framebuffer.write(backup)
                framebuffer.flush()

    print(
        f"已写入 {device}: {width}x{height}, {bpp}bpp, "
        f"stride={stride}, visible_row_bytes={visible_row_bytes}"
    )


def command_fill(args: argparse.Namespace) -> None:
    info = framebuffer_info(args.device)
    width = int(info["width"])
    stride = int(info["stride"])
    bpp = int(info["bitsPerPixel"])
    pixel = pixel_for_bpp(args.color, bpp)
    row = pixel * width
    row += b"\x00" * (stride - len(row))
    fill_rows(args.device, [row], args.duration, args.restore)


def command_bars(args: argparse.Namespace) -> None:
    info = framebuffer_info(args.device)
    width = int(info["width"])
    stride = int(info["stride"])
    bpp = int(info["bitsPerPixel"])
    colors = [
        parse_color("#ff2d55"),
        parse_color("#ffd60a"),
        parse_color("#30d158"),
        parse_color("#0a84ff"),
        parse_color("#bf5af2"),
    ]
    row = bytearray()
    for x in range(width):
        color = colors[(x * len(colors)) // max(width, 1)]
        row.extend(pixel_for_bpp(color, bpp))
    row.extend(b"\x00" * (stride - len(row)))
    fill_rows(args.device, [bytes(row)], args.duration, args.restore)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="读取 Linux 显示信息，或直接向 /dev/fb0 写入纯色/色条测试画面。"
    )
    parser.add_argument("--device", default="/dev/fb0", help="framebuffer 设备路径，默认 /dev/fb0")

    subparsers = parser.add_subparsers(dest="command", required=True)
    info = subparsers.add_parser("info", help="输出 framebuffer 和 DRM connector 信息")
    info.set_defaults(func=lambda args: print_info(args.device))

    fill = subparsers.add_parser("fill", help="将 framebuffer 填充为指定颜色")
    fill.add_argument("--color", required=True, type=parse_color, help="颜色，例如 #0047ff 或 blue")
    fill.add_argument("--duration", type=float, help="保持秒数；不传则持续显示")
    fill.add_argument("--restore", action="store_true", help="结束时恢复写入前的 framebuffer 内容")
    fill.set_defaults(func=command_fill)

    bars = subparsers.add_parser("bars", help="显示一组彩色色条")
    bars.add_argument("--duration", type=float, help="保持秒数；不传则持续显示")
    bars.add_argument("--restore", action="store_true", help="结束时恢复写入前的 framebuffer 内容")
    bars.set_defaults(func=command_bars)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except PermissionError as exc:
        print(f"权限不足: {exc}", file=sys.stderr)
        print("提示：使用 sudo 运行，或将当前用户加入 video 组后重新登录。", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
