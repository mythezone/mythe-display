#!/usr/bin/env python3
"""Serve the static Mythe Display web kiosk test page."""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 Mythe Display 静态网页测试服务。")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=4173, help="监听端口，默认 4173")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1] / "public"),
        help="静态文件根目录，默认仓库 public/",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"静态目录不存在: {root}")

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
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
