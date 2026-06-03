#!/usr/bin/env python3
"""
Control the running Mythe Display Chromium kiosk through the local DevTools API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
from urllib.request import ProxyHandler, Request, build_opener


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="控制正在运行的 Mythe Display Chromium kiosk，不重启 systemd 服务。"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MYTHE_DISPLAY_REMOTE_DEBUG_HOST", "127.0.0.1"),
        help="DevTools HTTP host，默认 127.0.0.1。",
    )
    parser.add_argument(
        "--port",
        type=positive_int,
        default=int(os.environ.get("MYTHE_DISPLAY_REMOTE_DEBUG_PORT", "23458")),
        help="DevTools HTTP port，默认 23458。",
    )
    parser.add_argument(
        "--web-host",
        default=os.environ.get("MYTHE_DISPLAY_HOST", "127.0.0.1"),
        help="相对 URL 转绝对 URL 时使用的 Web host。",
    )
    parser.add_argument(
        "--web-port",
        type=positive_int,
        default=int(os.environ.get("MYTHE_DISPLAY_PORT", "23456")),
        help="相对 URL 转绝对 URL 时使用的 Web port。",
    )
    parser.add_argument("--timeout", type=float, default=3.0, help="HTTP 超时时间，单位秒。")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果。")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出当前 Chromium page target。")
    list_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    current_parser = subparsers.add_parser("current", help="输出当前 kiosk page target。")
    current_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    switch_parser = subparsers.add_parser("switch", help="切换当前 kiosk 到指定 URL。")
    switch_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    switch_parser.add_argument("url", help="目标 URL，也可以是 /kiosk-test/ 这类本地路径。")
    switch_parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="保留旧页面。默认关闭旧 page target。",
    )
    switch_parser.add_argument(
        "--cache-bust",
        action="store_true",
        help="在 URL 上追加 assetCacheBust 参数，强制主题资源重新加载。",
    )

    open_parser = subparsers.add_parser("open", help="打开新 URL 并保留旧页面。")
    open_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    open_parser.add_argument("url", help="目标 URL，也可以是 /kiosk-test/ 这类本地路径。")
    open_parser.add_argument(
        "--cache-bust",
        action="store_true",
        help="在 URL 上追加 assetCacheBust 参数，强制主题资源重新加载。",
    )

    reload_parser = subparsers.add_parser("reload", help="刷新当前 kiosk 页面，不重启服务。")
    reload_parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    reload_parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="保留刷新前的旧页面。默认关闭旧 page target。",
    )
    reload_parser.add_argument(
        "--no-cache-bust",
        action="store_true",
        help="不追加 assetCacheBust 参数。默认会追加以刷新主题资源。",
    )

    return parser


def request(
    opener: Any,
    base_url: str,
    path: str,
    timeout: float,
    method: str = "GET",
) -> tuple[int, str]:
    req = Request(f"{base_url}{path}", method=method)
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


def page_targets(targets: Any) -> list[dict[str, Any]]:
    if not isinstance(targets, list):
        return []
    return [target for target in targets if target.get("type") == "page"]


def normalize_target_url(value: str, web_host: str, web_port: int) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return value
    if value.startswith("/"):
        return f"http://{web_host}:{web_port}{value}"
    return f"http://{web_host}:{web_port}/{value.lstrip('/')}"


def with_cache_bust(url: str) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["assetCacheBust"] = str(int(time.time() * 1000))
    return urlunparse(parsed._replace(query=urlencode(params)))


def get_pages(opener: Any, base_url: str, timeout: float) -> list[dict[str, Any]]:
    return page_targets(request_json(opener, base_url, "/json", timeout))


def first_page(pages: list[dict[str, Any]]) -> dict[str, Any]:
    if not pages:
        raise RuntimeError("没有发现 page target。")
    return pages[0]


def navigate(
    opener: Any,
    base_url: str,
    target_url: str,
    timeout: float,
    close_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    encoded_url = quote(target_url, safe="")
    new_target = request_json(opener, base_url, f"/json/new?{encoded_url}", timeout, method="PUT")
    if not isinstance(new_target, dict) or "id" not in new_target:
        raise RuntimeError(f"创建新 page target 失败: {new_target}")

    new_target_id = str(new_target["id"])
    request(opener, base_url, f"/json/activate/{new_target_id}", timeout)

    for target in close_targets:
        target_id = target.get("id")
        if target_id and target_id != new_target_id:
            request(opener, base_url, f"/json/close/{target_id}", timeout)

    return new_target


def render_targets(targets: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
        return
    if not targets:
        print("没有发现 page target。")
        return
    for target in targets:
        print(f"{target.get('id', '-')}\t{target.get('title', '-')}\t{target.get('url', '-')}")


def render_result(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    action = payload.get("action", "control")
    url = payload.get("url", "-")
    print(f"已执行 {action}: {url}")


def main() -> int:
    args = build_parser().parse_args()
    base_url = f"http://{args.host}:{args.port}"
    opener = build_opener(ProxyHandler({}))

    try:
        pages = get_pages(opener, base_url, args.timeout)

        if args.command == "list":
            render_targets(pages, args.json)
            return 0

        if args.command == "current":
            render_targets([first_page(pages)], args.json)
            return 0

        if args.command == "switch":
            target_url = normalize_target_url(args.url, args.web_host, args.web_port)
            if args.cache_bust:
                target_url = with_cache_bust(target_url)
            new_target = navigate(
                opener,
                base_url,
                target_url,
                args.timeout,
                [] if args.keep_existing else pages,
            )
            render_result({"action": "switch", "url": target_url, "target": new_target}, args.json)
            return 0

        if args.command == "open":
            target_url = normalize_target_url(args.url, args.web_host, args.web_port)
            if args.cache_bust:
                target_url = with_cache_bust(target_url)
            new_target = navigate(opener, base_url, target_url, args.timeout, [])
            render_result({"action": "open", "url": target_url, "target": new_target}, args.json)
            return 0

        if args.command == "reload":
            current = first_page(pages)
            current_url = current.get("url") or normalize_target_url("/kiosk-test/", args.web_host, args.web_port)
            target_url = current_url if args.no_cache_bust else with_cache_bust(current_url)
            new_target = navigate(
                opener,
                base_url,
                target_url,
                args.timeout,
                [] if args.keep_existing else pages,
            )
            render_result({"action": "reload", "url": target_url, "target": new_target}, args.json)
            return 0

    except Exception as exc:  # noqa: BLE001
        print(
            "无法控制 kiosk Chromium。\n"
            f"目标: {base_url}\n"
            "请确认 kiosk 由 scripts/run-kiosk-web-test.sh 或 mythe-display-kiosk.service 启动，"
            "并且 MYTHE_DISPLAY_REMOTE_DEBUG_PORT 一致。\n"
            f"错误: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"未知命令: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
