#!/usr/bin/env python3
"""Serve the static Mythe Display web kiosk test page."""

from __future__ import annotations

import argparse
import functools
import json
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
        if parsed.path == "/runtime/faio-listen.json":
            if self.handle_faio_snapshot_override(head_only=False):
                return
        if parsed.path.startswith("/faio-listen/"):
            self.handle_faio_proxy(parsed, head_only=False)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        parsed = parse.urlparse(self.path)
        if parsed.path == "/runtime/faio-listen.json":
            if self.handle_faio_snapshot_override(head_only=True):
                return
        if parsed.path.startswith("/faio-listen/"):
            self.handle_faio_proxy(parsed, head_only=True)
            return
        super().do_HEAD()

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

    def resolve_faio_upstream_path(self, path: str, snapshot: dict, room_id: str) -> str:
        quoted_room = parse.quote(room_id)
        if path == "/faio-listen/media/current":
            playback = snapshot.get("playback") if isinstance(snapshot.get("playback"), dict) else {}
            file_id = str(playback.get("fileId") or "")
            if not file_id:
                return ""
            return f"/music/rooms/{quoted_room}/media/{parse.quote(file_id)}"
        prefix = "/faio-listen/media/"
        if path.startswith(prefix):
            file_id = parse.unquote(path[len(prefix) :]).strip("/")
            return f"/music/rooms/{quoted_room}/media/{parse.quote(file_id)}" if file_id else ""
        prefix = "/faio-listen/cover/"
        if path.startswith(prefix):
            file_id = parse.unquote(path[len(prefix) :]).strip("/")
            return f"/music/rooms/{quoted_room}/cover/{parse.quote(file_id)}" if file_id else ""
        return ""

    def proxy_faio_request(self, base_url: str, upstream_path: str, cookie_header: str, *, head_only: bool) -> None:
        headers = {
            "Cookie": cookie_header,
            "User-Agent": "MytheDisplay/0.1 faio-listen-proxy",
            "Accept": self.headers.get("Accept", "*/*"),
        }
        range_header = self.headers.get("Range")
        if range_header:
            headers["Range"] = range_header
        upstream_url = parse.urljoin(f"{base_url}/", upstream_path.lstrip("/"))
        upstream_request = request.Request(upstream_url, headers=headers, method="GET")
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
