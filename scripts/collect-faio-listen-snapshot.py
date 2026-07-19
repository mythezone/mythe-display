#!/usr/bin/env python3
"""
Collect a read-only FAIO listening-room snapshot for the kiosk widget.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROOM_URL = "http://127.0.0.1:4173/listen/XatSqhcP6LmROQyKrjCULXyD-zcynwRZO5QaLO5Oeyg"
DEFAULT_REFRESH_MS = 10_000
ROOM_COOKIE_NAME = "faio_music_room_session"


class FaioListenError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="采集 FAIO 一起听歌房间快照。")
    parser.add_argument(
        "--room-url",
        default=os.environ.get("MYTHE_DISPLAY_FAIO_LISTEN_ROOM_URL", DEFAULT_ROOM_URL),
        help="FAIO /listen/<room-id> 房间 URL。",
    )
    parser.add_argument(
        "--display-name",
        default=os.environ.get("MYTHE_DISPLAY_FAIO_LISTEN_DISPLAY_NAME", "MytheNAS"),
        help="加入房间时使用的显示名。",
    )
    parser.add_argument(
        "--passcode",
        default=os.environ.get("MYTHE_DISPLAY_FAIO_LISTEN_PASSCODE", ""),
        help="显示名已锁定时使用的用户口令。",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("public/runtime/faio-listen.json"),
        help="输出 runtime JSON 路径。",
    )
    parser.add_argument(
        "--session-file",
        type=Path,
        default=Path(os.environ.get("MYTHE_DISPLAY_FAIO_SESSION_FILE", "tmp/faio-listen-session.json")),
        help="保存房间 session cookie 的私有文件，默认 tmp/faio-listen-session.json。",
    )
    parser.add_argument("--refresh-ms", type=int, default=DEFAULT_REFRESH_MS, help="建议刷新间隔。")
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出 JSON。")
    return parser


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, payload: dict[str, Any], *, pretty: bool = False, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        tmp_path = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2 if pretty else None)
        handle.write("\n")
    os.chmod(tmp_path, 0o600 if private else 0o644)
    tmp_path.replace(path)
    os.chmod(path, 0o600 if private else 0o644)


def parse_room_url(value: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise FaioListenError(f"无效 FAIO 房间 URL: {value}")
    segments = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(segments) < 2 or segments[0] != "listen" or not segments[1]:
        raise FaioListenError("FAIO 房间 URL 应形如 https://host/listen/<room-id>")
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url.rstrip("/"), segments[1]


def api_url(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(f"{base_url}/", path.lstrip("/"))


def read_json(opener: urllib.request.OpenerDirector, url: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "MytheDisplay/0.1 faio-listen-collector",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=20) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise FaioListenError(f"FAIO API {url} 返回 {exc.code}: {detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise FaioListenError(f"FAIO API {url} 请求失败: {exc}") from exc
    if "json" not in content_type.lower():
        raise FaioListenError(f"FAIO API {url} 返回非 JSON 内容: {content_type}")
    return json.loads(raw.decode("utf-8"))


def load_cookie_jar(session_file: Path) -> http.cookiejar.MozillaCookieJar:
    cookie_file = session_file.with_suffix(".cookies.txt")
    jar = http.cookiejar.MozillaCookieJar(str(cookie_file))
    if cookie_file.exists():
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
        except Exception:
            pass
    return jar


def has_room_cookie(jar: http.cookiejar.CookieJar, room_id: str) -> bool:
    for cookie in jar:
        if cookie.name == ROOM_COOKIE_NAME and room_id in cookie.path:
            return True
    return False


def save_session_metadata(session_file: Path, base_url: str, room_id: str, jar: http.cookiejar.MozillaCookieJar) -> None:
    cookie_file = session_file.with_suffix(".cookies.txt")
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    jar.filename = str(cookie_file)
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(cookie_file, 0o600)
    cookies = [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "secure": cookie.secure,
        }
        for cookie in jar
        if cookie.name == ROOM_COOKIE_NAME and room_id in cookie.path
    ]
    atomic_write_json(
        session_file,
        {
            "baseUrl": base_url,
            "roomId": room_id,
            "updatedAt": utc_now_iso(),
            "cookies": cookies,
        },
        private=True,
    )


def ensure_joined(
    opener: urllib.request.OpenerDirector,
    jar: http.cookiejar.MozillaCookieJar,
    *,
    base_url: str,
    room_id: str,
    display_name: str,
    passcode: str,
    session_file: Path,
) -> dict[str, Any]:
    display_name = display_name.strip() or "MytheNAS"
    if not has_room_cookie(jar, room_id):
        read_json(
            opener,
            api_url(base_url, f"/music/rooms/{urllib.parse.quote(room_id)}/join"),
            method="POST",
            body={"display_name": display_name, "passcode": passcode},
        )
        save_session_metadata(session_file, base_url, room_id, jar)
    try:
        return read_json(opener, api_url(base_url, f"/music/rooms/{urllib.parse.quote(room_id)}/snapshot"))
    except FaioListenError as exc:
        if "返回 401" not in str(exc) and "返回 403" not in str(exc):
            raise
        read_json(
            opener,
            api_url(base_url, f"/music/rooms/{urllib.parse.quote(room_id)}/join"),
            method="POST",
            body={"display_name": display_name, "passcode": passcode},
        )
        save_session_metadata(session_file, base_url, room_id, jar)
        return read_json(opener, api_url(base_url, f"/music/rooms/{urllib.parse.quote(room_id)}/snapshot"))


def parse_lyrics(raw: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    time_pattern = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
    metadata_pattern = re.compile(r"^\[[a-zA-Z]+:[^\]]*]$")
    for line in raw.splitlines():
        matches = list(time_pattern.finditer(line))
        text = time_pattern.sub("", line).strip()
        if not matches:
            if text and not metadata_pattern.match(text):
                parsed.append({"time": 999999, "text": text})
            continue
        for match in matches:
            minutes = int(match.group(1) or 0)
            seconds = int(match.group(2) or 0)
            fraction = match.group(3) or ""
            milliseconds = int(fraction) / (10 ** min(len(fraction), 3)) if fraction else 0
            parsed.append({"time": minutes * 60 + seconds + milliseconds, "text": text or "·"})
    return sorted(parsed, key=lambda item: item["time"])


def collect_lyrics(
    opener: urllib.request.OpenerDirector,
    *,
    base_url: str,
    room_id: str,
    playback: dict[str, Any],
) -> list[dict[str, Any]]:
    file_id = str(playback.get("file_id") or "")
    if not file_id or playback.get("source_type") == "external":
        return []
    payload = read_json(opener, api_url(base_url, f"/music/rooms/{urllib.parse.quote(room_id)}/lyrics/{urllib.parse.quote(file_id)}"))
    rows = payload.get("lyrics") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    preferred = next((item for item in rows if item.get("synced")), None) or (rows[0] if rows else None)
    if not isinstance(preferred, dict):
        return []
    return parse_lyrics(str(preferred.get("content") or ""))


def proxy_cover(file_id: str, revision: Any = "") -> str:
    if not file_id:
        return ""
    suffix = f"?v={urllib.parse.quote(str(revision))}" if revision != "" else ""
    return f"/faio-listen/cover/{urllib.parse.quote(file_id)}{suffix}"


def normalize_track(item: dict[str, Any], *, revision: Any = "") -> dict[str, Any]:
    file_id = str(item.get("file_id") or "")
    source_type = str(item.get("source_type") or "library")
    return {
        "fileId": file_id,
        "queueId": str(item.get("queue_id") or ""),
        "title": str(item.get("title") or "等待点歌"),
        "artist": str(item.get("artist") or ""),
        "albumTitle": str(item.get("album_title") or ""),
        "durationSeconds": float(item.get("duration_seconds") or 0),
        "contributorName": str(item.get("contributor_name") or ""),
        "sourceType": source_type,
        "coverUrl": str(item.get("external_cover_url") or item.get("cover_url") or "") if source_type == "external" else proxy_cover(file_id, revision),
    }


def normalize_snapshot(
    *,
    base_url: str,
    room_url: str,
    room_id: str,
    display_name: str,
    raw: dict[str, Any],
    lyrics: list[dict[str, Any]],
    refresh_ms: int,
) -> dict[str, Any]:
    room = raw.get("room") if isinstance(raw.get("room"), dict) else {}
    playback = raw.get("playback") if isinstance(raw.get("playback"), dict) else {}
    public_output = raw.get("public_output") if isinstance(raw.get("public_output"), dict) else {}
    revision = playback.get("revision", 0)
    file_id = str(playback.get("file_id") or "")
    source_type = str(playback.get("source_type") or "library")
    queue_rows = raw.get("queue") if isinstance(raw.get("queue"), list) else []
    participants = raw.get("participants") if isinstance(raw.get("participants"), list) else []
    media_url = str(playback.get("media_url") or "")
    if source_type != "external" and file_id:
        media_url = f"/faio-listen/media/{urllib.parse.quote(file_id)}?v={urllib.parse.quote(str(revision))}"
    cover_url = str(playback.get("cover_url") or "")
    if source_type != "external" and file_id:
        cover_url = proxy_cover(file_id, revision)
    return {
        "schemaVersion": 1,
        "generatedAt": utc_now_iso(),
        "source": "faio.musicRoom",
        "status": "connected",
        "refreshMs": max(5000, int(refresh_ms)),
        "roomUrl": room_url,
        "baseUrl": base_url,
        "roomId": room_id,
        "displayName": display_name,
        "room": {
            "name": str(room.get("name") or "一起听歌"),
            "ownerDisplayName": str(room.get("owner_display_name") or ""),
            "onlineCount": int(room.get("online_count") or len(participants)),
            "queueCount": int(room.get("queue_count") or len(queue_rows)),
            "shareUrl": room_url,
            "status": str(room.get("status") or "open"),
        },
        "playback": {
            "revision": int(revision or 0),
            "serverTime": str(playback.get("server_time") or ""),
            "status": str(playback.get("status") or "paused"),
            "pausedForEmpty": bool(playback.get("paused_for_empty")),
            "positionSeconds": float(playback.get("position_seconds") or 0),
            "anchorServerTime": str(playback.get("anchor_server_time") or ""),
            "fileId": file_id,
            "title": str(playback.get("title") or "等待点歌"),
            "artist": str(playback.get("artist") or ""),
            "albumTitle": str(playback.get("album_title") or ""),
            "durationSeconds": float(playback.get("duration_seconds") or 0),
            "coverUrl": cover_url,
            "mediaUrl": media_url,
            "contributorName": str(playback.get("contributor_name") or ""),
            "sourceType": source_type,
            "next": {
                "fileId": str(playback.get("next_file_id") or ""),
                "title": str(playback.get("next_title") or ""),
                "artist": str(playback.get("next_artist") or ""),
                "albumTitle": str(playback.get("next_album_title") or ""),
                "coverUrl": proxy_cover(str(playback.get("next_file_id") or ""), revision),
                "sourceType": str(playback.get("next_source_type") or "library"),
            },
        },
        "publicOutput": {
            "revision": int(public_output.get("revision") or 0),
            "playing": bool(public_output.get("playing", True)),
            "volume": max(0, min(100, int(public_output.get("volume", 70)))),
            "updatedAt": str(public_output.get("updated_at") or ""),
        },
        "lyrics": lyrics[:120],
        "queue": [normalize_track(item, revision=revision) for item in queue_rows[:12] if isinstance(item, dict)],
        "_upstream": {
            "playbackMediaPath": str(playback.get("media_url") or ""),
            "playbackCoverPath": str(playback.get("cover_url") or ""),
        },
    }


def error_payload(room_url: str, message: str, refresh_ms: int) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "generatedAt": utc_now_iso(),
        "source": "faio.musicRoom",
        "status": "error",
        "refreshMs": max(5000, int(refresh_ms)),
        "roomUrl": room_url,
        "room": {"name": "一起听歌", "onlineCount": 0, "queueCount": 0, "status": "unknown"},
        "playback": {
            "status": "paused",
            "positionSeconds": 0,
            "durationSeconds": 0,
            "title": "FAIO 房间不可用",
            "artist": message,
            "albumTitle": "",
            "coverUrl": "",
            "mediaUrl": "",
        },
        "publicOutput": {"revision": 0, "playing": False, "volume": 0, "updatedAt": ""},
        "lyrics": [],
        "queue": [],
        "error": message,
    }


def main() -> int:
    args = build_parser().parse_args()
    room_url = args.room_url.strip() or DEFAULT_ROOM_URL
    try:
        base_url, room_id = parse_room_url(room_url)
        jar = load_cookie_jar(args.session_file)
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        raw = ensure_joined(
            opener,
            jar,
            base_url=base_url,
            room_id=room_id,
            display_name=args.display_name,
            passcode=args.passcode,
            session_file=args.session_file,
        )
        playback = raw.get("playback") if isinstance(raw.get("playback"), dict) else {}
        try:
            lyrics = collect_lyrics(opener, base_url=base_url, room_id=room_id, playback=playback)
        except FaioListenError:
            lyrics = []
        save_session_metadata(args.session_file, base_url, room_id, jar)
        payload = normalize_snapshot(
            base_url=base_url,
            room_url=room_url,
            room_id=room_id,
            display_name=args.display_name,
            raw=raw,
            lyrics=lyrics,
            refresh_ms=args.refresh_ms,
        )
        atomic_write_json(args.out, payload, pretty=args.pretty)
        title = payload["playback"]["title"]
        artist = payload["playback"]["artist"]
        print(f"已写入 {args.out}: {payload['room']['name']} · {title} · {artist}")
        return 0
    except Exception as exc:
        message = str(exc)
        atomic_write_json(args.out, error_payload(room_url, message, args.refresh_ms), pretty=args.pretty)
        print(f"采集 FAIO 一起听歌失败: {message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
