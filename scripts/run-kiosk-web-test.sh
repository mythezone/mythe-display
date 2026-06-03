#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MYTHE_DISPLAY_PORT:-23456}"
HOST="${MYTHE_DISPLAY_HOST:-127.0.0.1}"
DEFAULT_URL="http://${HOST}:${PORT}/kiosk-test/"
URL="${1:-$DEFAULT_URL}"
SERVER_PID=""
KIOSK_PID=""

export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage:
  scripts/run-kiosk-web-test.sh [URL]

默认 URL:
  $DEFAULT_URL

示例:
  scripts/run-kiosk-web-test.sh
  scripts/run-kiosk-web-test.sh https://example.com

需要:
  cage
  chromium-browser / chromium / google-chrome / firefox / firefox-esr
EOF
  exit 0
fi

cleanup() {
  if [[ -n "$KIOSK_PID" ]]; then
    kill "$KIOSK_PID" >/dev/null 2>&1 || true
    wait "$KIOSK_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

has_command() {
  command -v "$1" >/dev/null 2>&1
}

first_command() {
  for candidate in "$@"; do
    if has_command "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

fail_environment() {
  cat >&2 <<EOF
$1

请在本机屏幕上的登录 TTY 中运行，不要使用 sudo：
  scripts/run-kiosk-web-test.sh

如果刚刚执行过 usermod，请先退出当前登录会话并重新登录，确认：
  id
  loginctl show-session "\$XDG_SESSION_ID" -p Active -p Remote -p Seat -p TTY

期望：
  用户组包含 video/render/input
  Active=yes
  Remote=no
  Seat=seat0
EOF
  exit 1
}

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  fail_environment "检测到脚本正在以 root/sudo 运行。cage/wlroots 需要当前本地登录用户的活动 seat；sudo 运行常见结果就是 Failed to start a DRM session。"
fi

if [[ "${MYTHE_DISPLAY_ALLOW_REMOTE_KIOSK:-0}" != "1" ]]; then
  if ! tty -s; then
    fail_environment "当前会话不是本地 TTY。SSH、VS Code Remote 或 Codex 后台会话通常没有可接管 HDMI 的活动 seat。"
  fi

  SESSION_ID="${XDG_SESSION_ID:-}"
  if [[ -z "$SESSION_ID" ]]; then
    fail_environment "当前会话缺少 XDG_SESSION_ID，无法确认 logind seat。"
  fi

  SESSION_REMOTE="$(loginctl show-session "$SESSION_ID" -p Remote --value 2>/dev/null || true)"
  SESSION_ACTIVE="$(loginctl show-session "$SESSION_ID" -p Active --value 2>/dev/null || true)"
  SESSION_SEAT="$(loginctl show-session "$SESSION_ID" -p Seat --value 2>/dev/null || true)"

  if [[ "$SESSION_REMOTE" == "yes" || "$SESSION_ACTIVE" != "yes" || -z "$SESSION_SEAT" ]]; then
    fail_environment "当前 logind session 不是本地活动 seat。Remote=${SESSION_REMOTE:-unknown}, Active=${SESSION_ACTIVE:-unknown}, Seat=${SESSION_SEAT:-empty}。"
  fi
fi

USER_GROUPS="$(id -nG)"
for required_group in video render input; do
  if [[ " $USER_GROUPS " != *" $required_group "* ]]; then
    fail_environment "当前用户组缺少 $required_group。"
  fi
done

if [[ "$URL" == "$DEFAULT_URL" ]]; then
  python3 "$ROOT_DIR/scripts/serve-web-test.py" --host "$HOST" --port "$PORT" &
  SERVER_PID="$!"
  sleep 0.6
  if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    wait "$SERVER_PID" || true
    cat >&2 <<EOF
本地测试服务启动失败: ${HOST}:${PORT}

如果端口被占用，可以换一个端口：
  MYTHE_DISPLAY_PORT=23457 scripts/run-kiosk-web-test.sh
EOF
    exit 1
  fi
fi

BROWSER="$(first_command chromium chromium-browser google-chrome firefox firefox-esr || true)"
if [[ -z "$BROWSER" ]]; then
  cat >&2 <<'EOF'
没有找到可用浏览器。

建议安装其一：
  sudo apt install chromium-browser
  sudo apt install firefox
EOF
  exit 1
fi

if ! has_command cage; then
  cat >&2 <<'EOF'
没有找到 cage。当前脚本需要 cage 提供无桌面 Wayland kiosk。

建议安装：
  sudo apt install cage

安装后重新运行：
  scripts/run-kiosk-web-test.sh
EOF
  exit 1
fi

if [[ "$BROWSER" == "firefox" || "$BROWSER" == "firefox-esr" ]]; then
  dbus-run-session -- cage -s -- env MOZ_ENABLE_WAYLAND=1 "$BROWSER" --kiosk "$URL" &
  KIOSK_PID="$!"
  set +e
  wait "$KIOSK_PID"
  KIOSK_STATUS="$?"
  set -e
  KIOSK_PID=""
  exit "$KIOSK_STATUS"
fi

USER_DATA_DIR="${MYTHE_DISPLAY_BROWSER_PROFILE:-/tmp/mythe-display-kiosk-profile}"
mkdir -p "$USER_DATA_DIR"

dbus-run-session -- cage -s -- "$BROWSER" \
  --kiosk "$URL" \
  --user-data-dir="$USER_DATA_DIR" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --proxy-bypass-list="<-loopback>" \
  --ozone-platform=wayland &
KIOSK_PID="$!"
set +e
wait "$KIOSK_PID"
KIOSK_STATUS="$?"
set -e
KIOSK_PID=""
exit "$KIOSK_STATUS"
