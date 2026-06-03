#!/usr/bin/env python3
"""
Switch the running kiosk Chromium page through the local DevTools HTTP API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import ProxyHandler, Request, build_opener


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="切换正在运行的 Mythe Display kiosk 页面 URL。"
    )
    parser.add_argument("url", nargs="?", help="目标 URL，也可以是 /kiosk-test/ 这类本地路径。")
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出当前 Chromium DevTools 页面，不执行切换。",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="创建新页面后保留旧页面。默认会关闭旧的 page target。",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MYTHE_DISPLAY_REMOTE_DEBUG_HOST", "127.0.0.1"),
        help="DevTools HTTP host，默认 127.0.0.1。",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MYTHE_DISPLAY_REMOTE_DEBUG_PORT", "23458")),
        help="DevTools HTTP port，默认 23458。",
    )
    parser.add_argument(
        "--web-host",
        default=os.environ.get("MYTHE_DISPLAY_HOST", "127.0.0.1"),
        help="当 url 是相对路径时使用的 Web host。",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=int(os.environ.get("MYTHE_DISPLAY_PORT", "23456")),
        help="当 url 是相对路径时使用的 Web port。",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="HTTP 超时时间，单位秒。")
    return parser


def request(
    opener: Any,
    base_url: str,
    path: str,
    timeout: float,
    method: str = "GET",
) -> tuple[int, str]:
    url = f"{base_url}{path}"
    req = Request(url, method=method)
    with opener.open(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def request_json(
    opener: Any,
    base_url: str,
    path: str,
    timeout: float,
    method: str = "GET",
) -> Any:
    _, body = request(opener, base_url, path, timeout, method)
    if not body.strip():
        return None
    return json.loads(body)


def page_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [target for target in targets if target.get("type") == "page"]


def normalize_target_url(value: str, web_host: str, web_port: int) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return value
    if value.startswith("/"):
        return f"http://{web_host}:{web_port}{value}"
    return f"http://{web_host}:{web_port}/{value.lstrip('/')}"


def print_targets(targets: list[dict[str, Any]]) -> None:
    if not targets:
        print("没有发现 page target。")
        return
    for target in targets:
        print(f"{target.get('id', '-')}\t{target.get('title', '-')}\t{target.get('url', '-')}")


def main() -> int:
    args = build_parser().parse_args()
    base_url = f"http://{args.host}:{args.port}"
    opener = build_opener(ProxyHandler({}))

    try:
        targets = page_targets(request_json(opener, base_url, "/json", args.timeout))
    except Exception as exc:  # noqa: BLE001
        print(
            "无法连接 kiosk DevTools 控制端口。\n"
            f"目标: {base_url}\n"
            "请确认 kiosk 是用 scripts/run-kiosk-web-test.sh 启动，并且 "
            "MYTHE_DISPLAY_REMOTE_DEBUG_PORT 与脚本参数一致。\n"
            f"错误: {exc}",
            file=sys.stderr,
        )
        return 1

    if args.list:
        print_targets(targets)
        return 0

    if not args.url:
        print("请提供目标 URL，或使用 --list 查看当前页面。", file=sys.stderr)
        return 2

    target_url = normalize_target_url(args.url, args.web_host, args.web_port)
    encoded_url = quote(target_url, safe="")

    try:
        new_target = request_json(
            opener,
            base_url,
            f"/json/new?{encoded_url}",
            args.timeout,
            method="PUT",
        )
        new_target_id = new_target["id"]
        request(opener, base_url, f"/json/activate/{new_target_id}", args.timeout)

        if not args.keep_existing:
            for target in targets:
                target_id = target.get("id")
                if target_id and target_id != new_target_id:
                    request(opener, base_url, f"/json/close/{target_id}", args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"切换 URL 失败: {exc}", file=sys.stderr)
        return 1

    print(f"已切换 kiosk 页面: {target_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
