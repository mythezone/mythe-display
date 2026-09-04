#!/usr/bin/env python3
"""
Follow the FAIO listening-room snapshot and play audio through ALSA.

Chromium can report an HTMLMediaElement as playing while never opening an ALSA
PCM device in the root, headless kiosk environment. This helper keeps audio
outside the browser and sends it directly to the configured ALSA endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urljoin


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT_DIR / "public/runtime/faio-listen.json"
DEFAULT_ALSA_DEVICE = os.environ.get("MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE", "plughw:0,3")
DEFAULT_BASE_URL = os.environ.get("MYTHE_DISPLAY_FAIO_AUDIO_BASE_URL", "http://127.0.0.1:23456")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通过 ALSA 播放 FAIO 一起听歌房间音频。")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT, help="FAIO runtime 快照路径。")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Mythe Display 本地 Web 服务地址。")
    parser.add_argument("--alsa-device", default=DEFAULT_ALSA_DEVICE, help="ALSA 输出设备，例如 plughw:0,3。")
    parser.add_argument("--poll-ms", type=int, default=int(os.environ.get("MYTHE_DISPLAY_FAIO_AUDIO_POLL_MS", "2000")))
    parser.add_argument(
        "--public-output-path",
        default=os.environ.get("MYTHE_DISPLAY_FAIO_PUBLIC_OUTPUT_PATH", "/faio-listen/public-output"),
        help="公共播放器暂停与音量控制端点。",
    )
    parser.add_argument(
        "--resume-public-output",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("MYTHE_DISPLAY_FAIO_RESUME_PUBLIC_OUTPUT", "1") != "0",
        help="启动时恢复 FAIO 公共扬声器播放；默认启用。",
    )
    parser.add_argument("--resume-only", action="store_true", help="恢复公共扬声器后退出。")
    parser.add_argument("--ffmpeg", default=os.environ.get("MYTHE_DISPLAY_FFMPEG", "ffmpeg"), help="ffmpeg 命令路径。")
    parser.add_argument("--log-level", default=os.environ.get("MYTHE_DISPLAY_FAIO_AUDIO_LOG_LEVEL", "warning"))
    parser.add_argument("--once", action="store_true", help="启动一次当前曲目后退出，主要用于调试。")
    return parser


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def read_snapshot(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return None
    except OSError as exc:
        print(f"[faio-audio] snapshot 不可读取: {exc}", file=sys.stderr)
        return None
    except json.JSONDecodeError as exc:
        print(f"[faio-audio] snapshot JSON 无效: {exc}", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def read_public_output(base_url: str, path: str) -> dict[str, Any] | None:
    endpoint = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    try:
        with request.urlopen(endpoint, timeout=3) as response:
            payload = json.load(response)
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[faio-audio] 公共播放控制读取失败: {exc}", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def resume_public_output(base_url: str, path: str) -> dict[str, Any] | None:
    endpoint = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    body = json.dumps({"playing": True}).encode("utf-8")
    update = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with request.urlopen(update, timeout=5) as response:
            payload = json.load(response)
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(f"[faio-audio] 恢复公共扬声器失败: {exc}", file=sys.stderr)
        return None
    return payload if isinstance(payload, dict) else None


def desired_position(playback: dict[str, Any]) -> float:
    base = float(playback.get("positionSeconds") or 0)
    duration = float(playback.get("durationSeconds") or 0)
    server_time = parse_time(playback.get("serverTime"))
    if playback.get("status") == "playing" and server_time:
        base += max(0.0, (utc_now() - server_time).total_seconds())
    if duration > 0:
        base = min(base, duration)
    return max(0.0, base)


def media_url(base_url: str, playback: dict[str, Any]) -> str:
    raw = str(playback.get("mediaUrl") or "")
    if not raw:
        return ""
    return raw if raw.startswith(("http://", "https://")) else urljoin(base_url.rstrip("/") + "/", raw.lstrip("/"))


def playback_key(playback: dict[str, Any], url: str, volume: int) -> str:
    file_id = str(playback.get("fileId") or "")
    revision = str(playback.get("revision") or "")
    return f"{file_id}:{revision}:{volume}:{url}"


def should_play(
    snapshot: dict[str, Any] | None,
    playback: dict[str, Any],
    public_output: dict[str, Any],
    source_url: str,
) -> bool:
    return bool(
        snapshot
        and snapshot.get("status") == "connected"
        and playback.get("status") == "playing"
        and public_output.get("playing", True) is not False
        and source_url
    )


def terminate(process: subprocess.Popen | None, *, timeout: float = 3.0) -> None:
    if not process or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def start_ffmpeg(
    *,
    ffmpeg: str,
    log_level: str,
    source_url: str,
    position: float,
    alsa_device: str,
    volume: int,
) -> subprocess.Popen:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        log_level,
        "-nostdin",
        "-ss",
        f"{position:.3f}",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        source_url,
        "-vn",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-af",
        f"volume={max(0, min(100, volume)) / 100:.2f}",
        "-f",
        "alsa",
        alsa_device,
    ]
    return subprocess.Popen(command)


def main() -> int:
    args = build_parser().parse_args()
    process: subprocess.Popen | None = None
    current_key = ""
    stopping = False

    def handle_signal(signum: int, _frame: Any) -> None:
        nonlocal stopping
        stopping = True
        terminate(process)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"[faio-audio] ALSA 输出设备: {args.alsa_device}")
    if args.resume_public_output or args.resume_only:
        resumed = resume_public_output(args.base_url, args.public_output_path)
        if resumed:
            print(f"[faio-audio] 公共扬声器已恢复，音量 {int(resumed.get('volume', 70))}%")
        if args.resume_only:
            return 0 if resumed else 1
    while not stopping:
        snapshot = read_snapshot(args.snapshot)
        playback = snapshot.get("playback") if isinstance(snapshot, dict) and isinstance(snapshot.get("playback"), dict) else {}
        snapshot_output = (
            snapshot.get("publicOutput")
            if isinstance(snapshot, dict) and isinstance(snapshot.get("publicOutput"), dict)
            else {}
        )
        public_output = read_public_output(args.base_url, args.public_output_path) or snapshot_output
        volume = max(0, min(100, int(public_output.get("volume", 70))))
        source_url = media_url(args.base_url, playback)
        if not should_play(snapshot, playback, public_output, source_url):
            if current_key:
                print("[faio-audio] 暂停或无可播放媒体，停止当前音频。")
            terminate(process)
            process = None
            current_key = ""
        else:
            key = playback_key(playback, source_url, volume)
            if process and process.poll() is not None:
                print(f"[faio-audio] ffmpeg 已退出，状态码 {process.returncode}。")
                process = None
                current_key = ""
            if key != current_key:
                terminate(process)
                position = desired_position(playback)
                title = str(playback.get("title") or "unknown")
                artist = str(playback.get("artist") or "")
                print(f"[faio-audio] 播放: {title} · {artist} @ {position:.1f}s · 音量 {volume}%")
                process = start_ffmpeg(
                    ffmpeg=args.ffmpeg,
                    log_level=args.log_level,
                    source_url=source_url,
                    position=position,
                    alsa_device=args.alsa_device,
                    volume=volume,
                )
                current_key = key
                if args.once:
                    return process.wait()
        time.sleep(max(0.5, args.poll_ms / 1000))

    terminate(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
