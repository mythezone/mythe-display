#!/usr/bin/env python3
"""Minimal DRM/KMS color test for a headless HDMI display."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import json
import mmap
import os
import re
import sys
import time
from pathlib import Path


DRM_ROOT = Path("/sys/class/drm")
DRM_MODE_CONNECTED = 1

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


def _ioc(direction: int, type_: str, nr: int, size: int) -> int:
    return (direction << 30) | (size << 16) | (ord(type_) << 8) | nr


def _iowr(type_: str, nr: int, struct_type: type[ctypes.Structure]) -> int:
    return _ioc(3, type_, nr, ctypes.sizeof(struct_type))


class DrmModeCardRes(ctypes.Structure):
    _fields_ = [
        ("fb_id_ptr", ctypes.c_uint64),
        ("crtc_id_ptr", ctypes.c_uint64),
        ("connector_id_ptr", ctypes.c_uint64),
        ("encoder_id_ptr", ctypes.c_uint64),
        ("count_fbs", ctypes.c_uint32),
        ("count_crtcs", ctypes.c_uint32),
        ("count_connectors", ctypes.c_uint32),
        ("count_encoders", ctypes.c_uint32),
        ("min_width", ctypes.c_uint32),
        ("max_width", ctypes.c_uint32),
        ("min_height", ctypes.c_uint32),
        ("max_height", ctypes.c_uint32),
    ]


class DrmModeModeInfo(ctypes.Structure):
    _fields_ = [
        ("clock", ctypes.c_uint32),
        ("hdisplay", ctypes.c_uint16),
        ("hsync_start", ctypes.c_uint16),
        ("hsync_end", ctypes.c_uint16),
        ("htotal", ctypes.c_uint16),
        ("hskew", ctypes.c_uint16),
        ("vdisplay", ctypes.c_uint16),
        ("vsync_start", ctypes.c_uint16),
        ("vsync_end", ctypes.c_uint16),
        ("vtotal", ctypes.c_uint16),
        ("vscan", ctypes.c_uint16),
        ("vrefresh", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("name", ctypes.c_char * 32),
    ]


class DrmModeGetConnector(ctypes.Structure):
    _fields_ = [
        ("encoders_ptr", ctypes.c_uint64),
        ("modes_ptr", ctypes.c_uint64),
        ("props_ptr", ctypes.c_uint64),
        ("prop_values_ptr", ctypes.c_uint64),
        ("count_modes", ctypes.c_uint32),
        ("count_props", ctypes.c_uint32),
        ("count_encoders", ctypes.c_uint32),
        ("encoder_id", ctypes.c_uint32),
        ("connector_id", ctypes.c_uint32),
        ("connector_type", ctypes.c_uint32),
        ("connector_type_id", ctypes.c_uint32),
        ("connection", ctypes.c_uint32),
        ("mm_width", ctypes.c_uint32),
        ("mm_height", ctypes.c_uint32),
        ("subpixel", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
    ]


class DrmModeGetEncoder(ctypes.Structure):
    _fields_ = [
        ("encoder_id", ctypes.c_uint32),
        ("encoder_type", ctypes.c_uint32),
        ("crtc_id", ctypes.c_uint32),
        ("possible_crtcs", ctypes.c_uint32),
        ("possible_clones", ctypes.c_uint32),
    ]


class DrmModeCrtc(ctypes.Structure):
    _fields_ = [
        ("set_connectors_ptr", ctypes.c_uint64),
        ("count_connectors", ctypes.c_uint32),
        ("crtc_id", ctypes.c_uint32),
        ("fb_id", ctypes.c_uint32),
        ("x", ctypes.c_uint32),
        ("y", ctypes.c_uint32),
        ("gamma_size", ctypes.c_uint32),
        ("mode_valid", ctypes.c_uint32),
        ("mode", DrmModeModeInfo),
    ]


class DrmModeCreateDumb(ctypes.Structure):
    _fields_ = [
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("bpp", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("handle", ctypes.c_uint32),
        ("pitch", ctypes.c_uint32),
        ("size", ctypes.c_uint64),
    ]


class DrmModeMapDumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
        ("offset", ctypes.c_uint64),
    ]


class DrmModeDestroyDumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
    ]


class DrmModeFbCmd(ctypes.Structure):
    _fields_ = [
        ("fb_id", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("pitch", ctypes.c_uint32),
        ("bpp", ctypes.c_uint32),
        ("depth", ctypes.c_uint32),
        ("handle", ctypes.c_uint32),
    ]


class DrmModeRmFb(ctypes.Structure):
    _fields_ = [
        ("fb_id", ctypes.c_uint32),
    ]


DRM_IOCTL_MODE_GETRESOURCES = _iowr("d", 0xA0, DrmModeCardRes)
DRM_IOCTL_MODE_GETCRTC = _iowr("d", 0xA1, DrmModeCrtc)
DRM_IOCTL_MODE_SETCRTC = _iowr("d", 0xA2, DrmModeCrtc)
DRM_IOCTL_MODE_GETENCODER = _iowr("d", 0xA6, DrmModeGetEncoder)
DRM_IOCTL_MODE_GETCONNECTOR = _iowr("d", 0xA7, DrmModeGetConnector)
DRM_IOCTL_MODE_ADDFB = _iowr("d", 0xAE, DrmModeFbCmd)
DRM_IOCTL_MODE_RMFB = _iowr("d", 0xAF, DrmModeRmFb)
DRM_IOCTL_MODE_CREATE_DUMB = _iowr("d", 0xB2, DrmModeCreateDumb)
DRM_IOCTL_MODE_MAP_DUMB = _iowr("d", 0xB3, DrmModeMapDumb)
DRM_IOCTL_MODE_DESTROY_DUMB = _iowr("d", 0xB4, DrmModeDestroyDumb)


def ioctl(fd: int, request: int, data: ctypes.Structure) -> ctypes.Structure:
    fcntl.ioctl(fd, request, data)
    return data


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


def mode_name(mode: DrmModeModeInfo) -> str:
    return bytes(mode.name).split(b"\0", 1)[0].decode("ascii", errors="replace")


def connector_sysfs_name(connector_id: int) -> str | None:
    for connector in DRM_ROOT.glob("card*-*"):
        try:
            raw = (connector / "connector_id").read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            continue
        if raw == str(connector_id):
            return connector.name
    return None


def get_resources(fd: int) -> tuple[list[int], list[int], list[int]]:
    res = DrmModeCardRes()
    ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, res)

    fbs = (ctypes.c_uint32 * res.count_fbs)()
    crtcs = (ctypes.c_uint32 * res.count_crtcs)()
    connectors = (ctypes.c_uint32 * res.count_connectors)()
    encoders = (ctypes.c_uint32 * res.count_encoders)()

    res.fb_id_ptr = ctypes.addressof(fbs)
    res.crtc_id_ptr = ctypes.addressof(crtcs)
    res.connector_id_ptr = ctypes.addressof(connectors)
    res.encoder_id_ptr = ctypes.addressof(encoders)
    ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, res)

    return list(crtcs), list(connectors), list(encoders)


def get_connector(fd: int, connector_id: int) -> tuple[DrmModeGetConnector, list[DrmModeModeInfo], list[int]]:
    connector = DrmModeGetConnector()
    connector.connector_id = connector_id
    ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, connector)

    modes = (DrmModeModeInfo * connector.count_modes)()
    encoders = (ctypes.c_uint32 * connector.count_encoders)()
    props = (ctypes.c_uint32 * connector.count_props)()
    prop_values = (ctypes.c_uint64 * connector.count_props)()

    connector.modes_ptr = ctypes.addressof(modes)
    connector.encoders_ptr = ctypes.addressof(encoders)
    connector.props_ptr = ctypes.addressof(props)
    connector.prop_values_ptr = ctypes.addressof(prop_values)
    ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, connector)
    return connector, list(modes), list(encoders)


def get_encoder(fd: int, encoder_id: int) -> DrmModeGetEncoder:
    encoder = DrmModeGetEncoder()
    encoder.encoder_id = encoder_id
    ioctl(fd, DRM_IOCTL_MODE_GETENCODER, encoder)
    return encoder


def get_crtc(fd: int, crtc_id: int) -> DrmModeCrtc:
    crtc = DrmModeCrtc()
    crtc.crtc_id = crtc_id
    ioctl(fd, DRM_IOCTL_MODE_GETCRTC, crtc)
    return crtc


def choose_connector(
    connectors: list[dict[str, object]], requested: str | None
) -> dict[str, object]:
    connected = [c for c in connectors if c["connection"] == DRM_MODE_CONNECTED]
    if requested:
        for connector in connectors:
            if requested in {str(connector["id"]), str(connector["name"])}:
                if connector["connection"] != DRM_MODE_CONNECTED:
                    raise RuntimeError(f"connector {requested} 未连接")
                return connector
        raise RuntimeError(f"找不到 connector: {requested}")
    if not connected:
        raise RuntimeError("没有已连接的 DRM connector")
    return connected[0]


def inspect_card(device: str) -> dict[str, object]:
    fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
    try:
        crtc_ids, connector_ids, encoder_ids = get_resources(fd)
        connectors: list[dict[str, object]] = []
        for connector_id in connector_ids:
            connector, modes, encoders = get_connector(fd, connector_id)
            connectors.append(
                {
                    "id": connector_id,
                    "name": connector_sysfs_name(connector_id),
                    "connection": connector.connection,
                    "connected": connector.connection == DRM_MODE_CONNECTED,
                    "encoderId": connector.encoder_id,
                    "encoders": encoders,
                    "mmWidth": connector.mm_width,
                    "mmHeight": connector.mm_height,
                    "modes": [
                        {
                            "name": mode_name(mode),
                            "width": mode.hdisplay,
                            "height": mode.vdisplay,
                            "refresh": mode.vrefresh,
                            "type": mode.type,
                        }
                        for mode in modes
                    ],
                }
            )
        encoders = []
        for encoder_id in encoder_ids:
            encoder = get_encoder(fd, encoder_id)
            encoders.append(
                {
                    "id": encoder_id,
                    "crtcId": encoder.crtc_id,
                    "possibleCrtcs": encoder.possible_crtcs,
                    "possibleClones": encoder.possible_clones,
                }
            )
        return {
            "device": device,
            "crtcs": crtc_ids,
            "connectors": connectors,
            "encoders": encoders,
        }
    finally:
        os.close(fd)


def find_mode(connector: dict[str, object], requested: str | None) -> DrmModeModeInfo:
    modes = connector["_raw_modes"]
    if not modes:
        raise RuntimeError("connector 没有可用显示模式")
    if requested:
        for mode in modes:
            if mode_name(mode) == requested:
                return mode
        raise RuntimeError(f"connector 不支持模式: {requested}")
    return modes[0]


def find_crtc_for_connector(
    fd: int,
    crtc_ids: list[int],
    connector: dict[str, object],
) -> int:
    encoder_ids = [int(value) for value in connector["_raw_encoders"]]
    if connector["encoderId"]:
        encoder_ids.insert(0, int(connector["encoderId"]))

    seen: set[int] = set()
    for encoder_id in encoder_ids:
        if encoder_id in seen:
            continue
        seen.add(encoder_id)
        encoder = get_encoder(fd, encoder_id)
        if encoder.crtc_id:
            return encoder.crtc_id
        for index, crtc_id in enumerate(crtc_ids):
            if encoder.possible_crtcs & (1 << index):
                return crtc_id
    raise RuntimeError("无法为 connector 找到可用 CRTC")


def build_scanout_rows(
    width: int,
    height: int,
    pitch: int,
    rgb: tuple[int, int, int],
    bars: bool,
) -> bytes:
    colors = [
        (255, 45, 85),
        (255, 214, 10),
        (48, 209, 88),
        (10, 132, 255),
        (191, 90, 242),
    ]
    data = bytearray(pitch * height)
    for y in range(height):
        row_start = y * pitch
        for x in range(width):
            red, green, blue = colors[(x * len(colors)) // max(width, 1)] if bars else rgb
            offset = row_start + x * 4
            data[offset : offset + 4] = bytes((blue, green, red, 0))
    return bytes(data)


def run_fill(args: argparse.Namespace, bars: bool = False) -> None:
    fd = os.open(args.device, os.O_RDWR | os.O_CLOEXEC)
    framebuffer_id = 0
    dumb_handle = 0
    mapped = None
    original_crtc = None
    try:
        crtc_ids, connector_ids, _ = get_resources(fd)

        connectors = []
        for connector_id in connector_ids:
            connector, modes, encoders = get_connector(fd, connector_id)
            connectors.append(
                {
                    "id": connector_id,
                    "name": connector_sysfs_name(connector_id),
                    "connection": connector.connection,
                    "encoderId": connector.encoder_id,
                    "_raw_modes": modes,
                    "_raw_encoders": encoders,
                }
            )

        connector = choose_connector(connectors, args.connector)
        mode = find_mode(connector, args.mode)
        crtc_id = find_crtc_for_connector(fd, crtc_ids, connector)
        original_crtc = get_crtc(fd, crtc_id)

        create = DrmModeCreateDumb()
        create.width = mode.hdisplay
        create.height = mode.vdisplay
        create.bpp = 32
        ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, create)
        dumb_handle = create.handle

        fb = DrmModeFbCmd()
        fb.width = mode.hdisplay
        fb.height = mode.vdisplay
        fb.pitch = create.pitch
        fb.bpp = 32
        fb.depth = 24
        fb.handle = dumb_handle
        ioctl(fd, DRM_IOCTL_MODE_ADDFB, fb)
        framebuffer_id = fb.fb_id

        map_request = DrmModeMapDumb()
        map_request.handle = dumb_handle
        ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, map_request)
        mapped = mmap.mmap(fd, create.size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=map_request.offset)
        mapped[:] = build_scanout_rows(mode.hdisplay, mode.vdisplay, create.pitch, args.color, bars)

        connector_array = (ctypes.c_uint32 * 1)(int(connector["id"]))
        set_crtc = DrmModeCrtc()
        set_crtc.set_connectors_ptr = ctypes.addressof(connector_array)
        set_crtc.count_connectors = 1
        set_crtc.crtc_id = crtc_id
        set_crtc.fb_id = framebuffer_id
        set_crtc.x = 0
        set_crtc.y = 0
        set_crtc.mode_valid = 1
        set_crtc.mode = mode
        ioctl(fd, DRM_IOCTL_MODE_SETCRTC, set_crtc)

        print(
            f"已设置 DRM scanout: connector={connector['name'] or connector['id']}, "
            f"crtc={crtc_id}, mode={mode_name(mode)}, fb={framebuffer_id}, "
            f"pitch={create.pitch}, size={create.size}",
            flush=True,
        )
        if args.duration is not None:
            time.sleep(args.duration)
    finally:
        if original_crtc is not None and args.restore:
            try:
                restore_connector_array = (ctypes.c_uint32 * 1)(int(connector["id"]))
                restore = DrmModeCrtc()
                restore.set_connectors_ptr = ctypes.addressof(restore_connector_array)
                restore.count_connectors = 1
                restore.crtc_id = original_crtc.crtc_id
                restore.fb_id = original_crtc.fb_id
                restore.x = original_crtc.x
                restore.y = original_crtc.y
                restore.mode_valid = original_crtc.mode_valid
                restore.mode = original_crtc.mode
                ioctl(fd, DRM_IOCTL_MODE_SETCRTC, restore)
            except OSError as exc:
                print(f"警告：恢复原 CRTC 失败: {exc}", file=sys.stderr)
        if mapped is not None:
            try:
                mapped.close()
            except OSError as exc:
                print(f"警告：关闭 mmap 失败: {exc}", file=sys.stderr)
        if framebuffer_id:
            try:
                ioctl(fd, DRM_IOCTL_MODE_RMFB, DrmModeRmFb(framebuffer_id))
            except OSError as exc:
                print(f"警告：删除 framebuffer 失败: {exc}", file=sys.stderr)
        if dumb_handle:
            try:
                ioctl(fd, DRM_IOCTL_MODE_DESTROY_DUMB, DrmModeDestroyDumb(dumb_handle))
            except OSError as exc:
                print(f"警告：销毁 dumb buffer 失败: {exc}", file=sys.stderr)
        os.close(fd)


def command_info(args: argparse.Namespace) -> None:
    print(json.dumps(inspect_card(args.device), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="直接使用 DRM/KMS 显示纯色或色条测试画面。")
    parser.add_argument("--device", default="/dev/dri/card0", help="DRM primary device，默认 /dev/dri/card0")

    subparsers = parser.add_subparsers(dest="command", required=True)
    info = subparsers.add_parser("info", help="输出 DRM resources/connectors/modes")
    info.set_defaults(func=command_info)

    fill = subparsers.add_parser("fill", help="通过 KMS 设置纯色 scanout")
    fill.add_argument("--color", required=True, type=parse_color, help="颜色，例如 #0047ff 或 blue")
    fill.add_argument("--connector", help="connector 名称或 ID，例如 card0-HDMI-A-2")
    fill.add_argument("--mode", help="显示模式名，例如 3840x1100；默认使用 connector 的第一个模式")
    fill.add_argument("--duration", type=float, help="保持秒数；不传则持续显示到进程退出")
    fill.add_argument("--restore", action="store_true", help="结束时恢复原 CRTC")
    fill.set_defaults(func=lambda args: run_fill(args, bars=False))

    bars = subparsers.add_parser("bars", help="通过 KMS 设置色条 scanout")
    bars.add_argument("--connector", help="connector 名称或 ID，例如 card0-HDMI-A-2")
    bars.add_argument("--mode", help="显示模式名，例如 3840x1100；默认使用 connector 的第一个模式")
    bars.add_argument("--duration", type=float, help="保持秒数；不传则持续显示到进程退出")
    bars.add_argument("--restore", action="store_true", help="结束时恢复原 CRTC")
    bars.set_defaults(func=lambda args: run_fill(args, bars=True))
    bars.set_defaults(color=(0, 0, 0))

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except PermissionError as exc:
        print(f"权限不足: {exc}", file=sys.stderr)
        print("提示：重新登录刷新 video 组权限，或用 sg video/sudo 运行。", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"DRM/KMS 错误: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
