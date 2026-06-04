#!/usr/bin/env python3
"""
Collect local Codex session/process metadata as a PixelAgentSnapshot.

This intentionally reads only session index metadata, not conversation bodies,
auth files, prompts, tool payloads, or message history.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = "public/runtime/codex-agents.json"
DEFAULT_REFRESH_MS = 300_000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user and sudo_user != "root":
        try:
            candidate = Path(pwd.getpwnam(sudo_user).pw_dir) / ".codex"
            if candidate.exists():
                return candidate
        except KeyError:
            pass

    return Path.home() / ".codex"


def run_text(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def codex_processes() -> list[dict[str, Any]]:
    try:
        output = run_text(["ps", "-eo", "pid,ppid,user,stat,comm,args"])
    except subprocess.CalledProcessError:
        return []

    rows = []
    for line in output.splitlines()[1:]:
        lower = line.lower()
        if "codex" not in lower:
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        pid, ppid, user, stat, comm, args = parts
        if "collect-codex-agents-snapshot" in args:
            continue
        rows.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "user": user,
                "stat": stat,
                "command": comm,
                "kind": process_kind(args),
            }
        )
    return rows


def process_kind(args: str) -> str:
    lower = args.lower()
    if "app-server proxy" in lower:
        return "proxy"
    if "app-server" in lower:
        return "app-server"
    if "mcp-server" in lower:
        return "mcp"
    return "codex"


def read_sessions(index_path: Path) -> list[dict[str, Any]]:
    if not index_path.exists():
        return []
    sessions = []
    with index_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            updated_at = parse_time(str(raw.get("updated_at") or ""))
            sessions.append(
                {
                    "id": str(raw.get("id") or ""),
                    "threadName": str(raw.get("thread_name") or "Codex Session"),
                    "updatedAt": updated_at,
                }
            )
    sessions.sort(key=lambda row: row["updatedAt"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return sessions


def age_label(updated_at: datetime | None, now: datetime) -> str:
    if not updated_at:
        return "unknown"
    seconds = max(0, int((now - updated_at).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86_400}d ago"


def status_for(updated_at: datetime | None, now: datetime, has_codex_process: bool) -> tuple[str, str]:
    if not updated_at:
        return "offline", "unknown"
    minutes = (now - updated_at).total_seconds() / 60
    if minutes <= 15 and has_codex_process:
        return "working", "recent activity"
    if minutes <= 120:
        return "thinking", "recent session"
    if minutes <= 24 * 60:
        return "idle", "idle"
    return "offline", "stale"


def truncate(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def short_process_kind(value: str) -> str:
    return {
        "app-server": "app",
        "proxy": "proxy",
        "mcp": "mcp",
        "codex": "codex",
    }.get(value, value[:8])


def collect(codex_home: Path, refresh_ms: int, limit: int, show_thread_names: bool) -> dict[str, Any]:
    now = utc_now()
    processes = codex_processes()
    sessions = read_sessions(codex_home / "session_index.jsonl")
    has_codex_process = bool(processes)
    agents = []
    process_kinds = sorted({row["kind"] for row in processes})

    if processes:
        agents.append(
            {
                "id": "codex-runtime",
                "name": "Codex Runtime",
                "project": "codex",
                "status": "working",
                "action": "working",
                "activity": f"{len(processes)} proc · {'/'.join(short_process_kind(kind) for kind in process_kinds) or 'codex'}",
                "updatedAt": now.isoformat(),
                "meta": {"source": "process"},
            }
        )

    remaining = max(0, limit - len(agents))
    for index, session in enumerate(sessions[:remaining]):
        status, activity = status_for(session["updatedAt"], now, has_codex_process)
        thread_name = truncate(session["threadName"], 34)
        meta = {"source": "session_index"}
        if show_thread_names:
            meta["threadName"] = thread_name
        agents.append(
            {
                "id": session["id"] or f"codex-session-{index + 1}",
                "name": thread_name if show_thread_names else f"Codex {index + 1}",
                "project": "codex",
                "status": status,
                "action": status,
                "activity": f"{activity} · {age_label(session['updatedAt'], now)}",
                "updatedAt": session["updatedAt"].isoformat() if session["updatedAt"] else None,
                "meta": meta,
            }
        )

    if not agents:
        agents.append(
            {
                "id": "codex-process",
                "name": "Codex",
                "project": "codex",
                "status": "working" if processes else "offline",
                "action": "working" if processes else "offline",
                "activity": f"{len(processes)} processes" if processes else "no local session index",
                "meta": {"source": "process"},
            }
        )

    return {
        "updatedAt": now.isoformat(),
        "refreshMs": refresh_ms,
        "source": "codex.local",
        "available": True,
        "summary": {
            "codexHome": str(codex_home),
            "sessionCount": len(sessions),
            "processCount": len(processes),
            "processKinds": process_kinds,
        },
        "agents": agents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Mythe Display Codex Agent JSON 快照。")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help=f"输出路径，默认 {DEFAULT_OUTPUT}。")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Codex 主目录，默认自动推断。")
    parser.add_argument("--refresh-ms", type=int, default=DEFAULT_REFRESH_MS, help="刷新周期元数据，默认 5 分钟。")
    parser.add_argument("--limit", type=int, default=4, help="输出 Agent 数量。")
    parser.add_argument(
        "--show-thread-names",
        action="store_true",
        default=os.environ.get("MYTHE_DISPLAY_CODEX_AGENT_SHOW_THREAD_NAMES") == "1",
        help="在 name/meta 中显示线程标题；也可设置 MYTHE_DISPLAY_CODEX_AGENT_SHOW_THREAD_NAMES=1。",
    )
    parser.add_argument("--pretty", action="store_true", help="使用缩进格式输出。")
    args = parser.parse_args()

    try:
        payload = collect(Path(args.codex_home).expanduser(), args.refresh_ms, max(1, args.limit), args.show_thread_names)
    except OSError as exc:
        print(f"采集 Codex Agent 失败: {exc}", file=sys.stderr)
        return 1

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None) + "\n",
        encoding="utf-8",
    )
    summary = payload["summary"]
    print(f"已写入 {output}: {summary['sessionCount']} sessions, {summary['processCount']} processes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
