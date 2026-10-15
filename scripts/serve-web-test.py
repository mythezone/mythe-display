#!/usr/bin/env python3
"""Serve the static Mythe Display web kiosk test page."""

from __future__ import annotations

import argparse
import functools
import json
import re
import math
import importlib.util
import os
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SESSION_FILE = ROOT_DIR / "tmp/faio-listen-session.json"
DEFAULT_SNAPSHOT_FILE = ROOT_DIR / "public/runtime/faio-listen.json"


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


class MytheDisplayHandler(SimpleHTTPRequestHandler):
    repo_root: Path = ROOT_DIR

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/faio-listen/karaoke/capabilities":
            self.send_json({"enabled": os.environ.get("MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT", "0") == "1", "continuous": True})
            return
        if parsed.path == "/faio-listen/karaoke/ws":
            self.handle_karaoke_websocket(parsed)
            return
        if parsed.path == "/faio-listen/karaoke/snapshot":
            self.handle_karaoke_clock(parsed)
            return
        if parsed.path == "/runtime/faio-listen.json":
            if self.handle_faio_snapshot_override(head_only=False):
                return
        if parsed.path.startswith("/faio-listen/"):
            self.handle_faio_proxy(parsed, head_only=False)
            return
        super().do_GET()

    def send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_karaoke_websocket(self, parsed: parse.ParseResult) -> None:
        if os.environ.get("MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT", "0") != "1":
            self.send_error(403, "Karaoke output is disabled")
            return
        # Output is a separately opted-in loopback kiosk facility. Do not expose
        # the privileged service room session as a LAN audio relay.
        origin = parse.urlsplit(self.headers.get("Origin", ""))
        if self.client_address[0] not in {"127.0.0.1", "::1"} or origin.scheme not in {"http", "https"} or origin.netloc != self.headers.get("Host", ""):
            self.send_error(403, "Same-origin local kiosk required")
            return
        client = parse.parse_qs(parsed.query).get("client_id", [""])[0]
        mode = parse.parse_qs(parsed.query).get("mode", [""])[0]
        if mode not in {"", "events"}:
            self.send_error(400, "Invalid WebSocket mode")
            return
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", client) or self.headers.get("Upgrade", "").lower() != "websocket" or self.headers.get("Sec-WebSocket-Version") != "13":
            self.send_error(400, "Invalid WebSocket request")
            return
        spec = importlib.util.spec_from_file_location("karaoke_ws_bridge", ROOT_DIR / "scripts/karaoke-ws-bridge.py")
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        upstream = None
        upgraded = False
        try:
            accept = bridge.accept_key(self.headers.get("Sec-WebSocket-Key", ""))
            session = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SESSION_FILE", DEFAULT_SESSION_FILE)))
            base = str(session.get("baseUrl") or "").rstrip("/")
            room = str(session.get("roomId") or "")
            cookie = self.faio_cookie_header(session)
            if not base or not room or not cookie:
                raise PermissionError("Existing session unavailable")
            upstream = bridge.connect_upstream(base, f"/music/rooms/{parse.quote(room, safe='')}/karaoke/ws?client_id={parse.quote(client)}" + ("&mode=events" if mode else ""), cookie)
            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            upgraded = True
            bridge.relay(self.connection, upstream, lifetime=None if mode == "events" else 1800)
        except (PermissionError, FileNotFoundError):
            if not upgraded:
                self.send_error(403, "Karaoke session unavailable")
        except (OSError, ValueError):
            if not upgraded:
                self.send_error(502, "Karaoke connection unavailable")
        finally:
            self.close_connection = True
            if upstream:
                upstream.close()

    def local_karaoke_session(self):
        origin_header = self.headers.get("Origin", "")
        origin = parse.urlsplit(origin_header)
        if (os.environ.get("MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT", "0") != "1"
                or self.client_address[0] not in {"127.0.0.1", "::1"}
                or (origin_header and (origin.scheme not in {"http", "https"} or origin.netloc != self.headers.get("Host", "")))):
            raise PermissionError("Same-origin local output required")
        session = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SESSION_FILE", DEFAULT_SESSION_FILE)))
        base, room, cookie = str(session.get("baseUrl") or "").rstrip("/"), str(session.get("roomId") or ""), self.faio_cookie_header(session)
        if not base or not room or not cookie:
            raise PermissionError("Existing session unavailable")
        return base, room, cookie

    def handle_karaoke_clock(self, parsed):
        try:
            base, room, cookie = self.local_karaoke_session()
            ping = float(parse.parse_qs(parsed.query).get("ping", [""])[0])
            if not math.isfinite(ping):
                raise ValueError("Invalid ping")
            self.proxy_faio_request(base, f"/music/rooms/{parse.quote(room, safe='')}/karaoke/snapshot?continuous=true&ping={ping}", cookie, head_only=False)
        except PermissionError:
            self.send_error(403, "Local output session required")
        except (OSError, ValueError):
            self.send_error(400, "Invalid clock request")

    def do_POST(self):
        if parse.urlsplit(self.path).path != "/faio-listen/playback-progress":
            self.send_error(405, "Method not allowed")
            return
        try:
            base, room, cookie = self.local_karaoke_session()
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Invalid report size")
            payload = json.loads(self.rfile.read(length))
            fields = {"protocol", "client_id", "report_seq", "instance", "transport_token", "position_seconds", "playback_status"}
            if not isinstance(payload, dict) or set(payload) != fields or payload["protocol"] != 2:
                raise ValueError("Invalid progress report")
            self.proxy_faio_request(base, f"/music/rooms/{parse.quote(room, safe='')}/playback-progress", cookie,
                head_only=False, method="POST", body=json.dumps(payload).encode("utf-8"), content_type="application/json")
        except PermissionError:
            self.send_error(403, "Local output session required")
        except (OSError, ValueError):
            self.send_error(400, "Invalid progress report")

    def do_HEAD(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/runtime/faio-listen.json":
            if self.handle_faio_snapshot_override(head_only=True):
                return
        if parsed.path.startswith("/faio-listen/"):
            self.handle_faio_proxy(parsed, head_only=True)
            return
        super().do_HEAD()

    def do_PUT(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/faio-listen/public-output":
            self.handle_faio_public_output_update(parsed)
            return
        self.send_error(405, "Method not allowed")

    def handle_faio_snapshot_override(self, *, head_only: bool) -> bool:
        override = os.environ.get("MYTHE_DISPLAY_FAIO_SNAPSHOT_FILE")
        if not override:
            return False
        path = repo_path(override)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "FAIO listen snapshot override is not ready")
            return True
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(data)
        return True

    def handle_faio_proxy(self, parsed: parse.ParseResult, *, head_only: bool) -> None:
        try:
            snapshot = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SNAPSHOT_FILE", DEFAULT_SNAPSHOT_FILE)))
            if parsed.path == "/faio-listen/public-output":
                self.handle_faio_public_output(snapshot, head_only=head_only)
                return
            session = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SESSION_FILE", DEFAULT_SESSION_FILE)))
            base_url = str(session.get("baseUrl") or snapshot.get("baseUrl") or "").rstrip("/")
            room_id = str(session.get("roomId") or snapshot.get("roomId") or "")
            upstream_path = self.resolve_faio_upstream_path(parsed.path, snapshot, room_id)
            if not base_url or not room_id or not upstream_path:
                self.send_error(404, "FAIO listen media is not available")
                return
            cookie_header = self.faio_cookie_header(session)
            if not cookie_header:
                self.send_error(503, "FAIO listen session is not ready")
                return
            self.proxy_faio_request(base_url, upstream_path, cookie_header, head_only=head_only)
        except FileNotFoundError:
            self.send_error(503, "FAIO listen snapshot is not ready")
        except Exception as exc:
            self.log_error("FAIO listen proxy failed: %s", exc)
            self.send_error(502, "FAIO listen proxy failed")

    def handle_faio_public_output(self, snapshot: dict, *, head_only: bool) -> None:
        payload = snapshot.get("publicOutput") if isinstance(snapshot.get("publicOutput"), dict) else {}
        body = json.dumps(
            {
                "revision": int(payload.get("revision") or 0),
                "playing": payload.get("playing", True) is not False,
                "volume": max(0, min(100, int(payload.get("volume", 70)))),
                "updatedAt": str(payload.get("updatedAt") or payload.get("updated_at") or ""),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def handle_faio_public_output_update(self, parsed: parse.ParseResult) -> None:
        try:
            snapshot = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SNAPSHOT_FILE", DEFAULT_SNAPSHOT_FILE)))
            session = self.read_json(repo_path(os.environ.get("MYTHE_DISPLAY_FAIO_SESSION_FILE", DEFAULT_SESSION_FILE)))
            base_url = str(session.get("baseUrl") or snapshot.get("baseUrl") or "").rstrip("/")
            room_id = str(session.get("roomId") or snapshot.get("roomId") or "")
            cookie_header = self.faio_cookie_header(session)
            content_length = min(4096, max(0, int(self.headers.get("Content-Length", "0"))))
            body = self.rfile.read(content_length)
            payload = json.loads(body or b"{}")
            if not isinstance(payload, dict) or not set(payload).issubset({"playing", "volume"}):
                self.send_error(400, "Invalid public output payload")
                return
            if not base_url or not room_id or not cookie_header:
                self.send_error(503, "FAIO listen session is not ready")
                return
            upstream_path = self.resolve_faio_upstream_path(parsed.path, snapshot, room_id)
            self.proxy_faio_request(
                base_url,
                upstream_path,
                cookie_header,
                head_only=False,
                method="PUT",
                body=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
            )
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            self.send_error(503, "FAIO listen session is not ready")

    def resolve_faio_upstream_path(self, path: str, snapshot: dict, room_id: str) -> str:
        quoted_room = parse.quote(room_id)
        if path == "/faio-listen/public-output":
            return f"/music/rooms/{quoted_room}/public-output"
        if path == "/faio-listen/media/current":
            playback = snapshot.get("playback") if isinstance(snapshot.get("playback"), dict) else {}
            file_id = str(playback.get("fileId") or "")
            if not file_id:
                return ""
            return f"/music/rooms/{quoted_room}/media/{parse.quote(file_id)}"
        prefix = "/faio-listen/karaoke/assets/"
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if os.environ.get("MYTHE_DISPLAY_ENABLE_KARAOKE_OUTPUT", "0") == "1" and self.client_address[0] in {"127.0.0.1", "::1"} and re.fullmatch(r"[A-Za-z0-9_-]{1,100}/[A-Za-z0-9_-]{1,100}\.wav", suffix):
                return f"/music/rooms/{quoted_room}/karaoke/assets/" + suffix
            karaoke = snapshot.get("karaoke") if isinstance(snapshot.get("karaoke"), dict) else {}
            if karaoke.get("connectionStatus") != "connected":
                return ""
            for version in karaoke.get("versions", []):
                for role in ("original", "accompaniment"):
                    for chunk in version.get("tracks", {}).get(role, []):
                        if chunk.get("url") == path:
                            return f"/music/rooms/{quoted_room}/karaoke/assets/" + path[len(prefix):]
            return ""
        prefix = "/faio-listen/media/"
        if path.startswith(prefix):
            file_id = parse.unquote(path[len(prefix) :]).strip("/")
            return f"/music/rooms/{quoted_room}/media/{parse.quote(file_id)}" if file_id else ""
        prefix = "/faio-listen/cover/"
        if path.startswith(prefix):
            file_id = parse.unquote(path[len(prefix) :]).strip("/")
            return f"/music/rooms/{quoted_room}/cover/{parse.quote(file_id)}" if file_id else ""
        prefix = "/faio-listen/online/"
        if path.startswith(prefix):
            parts = [parse.unquote(part) for part in path[len(prefix) :].split("/") if part]
            if len(parts) != 2 or parts[1] not in {"media", "cover"}:
                return ""
            online_id, asset_type = parts
            return (
                f"/music/rooms/{quoted_room}/online/{parse.quote(online_id)}/{asset_type}"
                if online_id
                else ""
            )
        return ""

    def proxy_faio_request(
        self,
        base_url: str,
        upstream_path: str,
        cookie_header: str,
        *,
        head_only: bool,
        method: str = "GET",
        body: bytes | None = None,
        content_type: str = "",
    ) -> None:
        headers = {
            "Cookie": cookie_header,
            "User-Agent": "MytheDisplay/0.1 faio-listen-proxy",
            "Accept": self.headers.get("Accept", "*/*"),
        }
        range_header = self.headers.get("Range")
        if range_header:
            headers["Range"] = range_header
        if content_type:
            headers["Content-Type"] = content_type
        upstream_url = parse.urljoin(f"{base_url}/", upstream_path.lstrip("/"))
        upstream_request = request.Request(
            upstream_url,
            data=body,
            headers=headers,
            method="HEAD" if head_only else method,
        )
        try:
            upstream = request.urlopen(upstream_request, timeout=30)
        except error.HTTPError as exc:
            self.send_response(exc.code)
            self.copy_upstream_headers(exc.headers)
            self.end_headers()
            return
        except error.URLError as exc:
            self.log_error("FAIO upstream unavailable: %s", exc)
            self.send_error(502, "FAIO upstream unavailable")
            return
        with upstream:
            self.send_response(upstream.getcode())
            self.copy_upstream_headers(upstream.headers)
            self.end_headers()
            if not head_only:
                try:
                    shutil.copyfileobj(upstream, self.wfile, length=256 * 1024)
                except (BrokenPipeError, ConnectionResetError):
                    return

    def copy_upstream_headers(self, headers) -> None:
        blocked = {
            "connection",
            "transfer-encoding",
            "content-encoding",
            "set-cookie",
            "server",
            "date",
            "cache-control",
        }
        for key, value in headers.items():
            if key.lower() in blocked:
                continue
            self.send_header(key, value)
        self.send_header("Cache-Control", "private, no-store")

    @staticmethod
    def faio_cookie_header(session: dict) -> str:
        cookies = session.get("cookies")
        if not isinstance(cookies, list):
            return ""
        pairs = []
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "")
            if name and value:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)

    @staticmethod
    def read_json(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 Mythe Display 静态网页测试服务。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=23456, help="监听端口，默认 23456")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1] / "public"),
        help="静态文件根目录，默认仓库 public/",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"静态目录不存在: {root}")

    handler = functools.partial(MytheDisplayHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Mythe Display web test: http://{args.host}:{args.port}/kiosk-test/")
    print(f"Serving: {root}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
