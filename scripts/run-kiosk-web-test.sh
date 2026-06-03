#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${MYTHE_DISPLAY_PORT:-4173}"
HOST="${MYTHE_DISPLAY_HOST:-127.0.0.1}"
DEFAULT_URL="http://${HOST}:${PORT}/kiosk-test/"
URL="${1:-$DEFAULT_URL}"
SERVER_PID=""

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

if [[ "$URL" == "$DEFAULT_URL" ]]; then
  python3 "$ROOT_DIR/scripts/serve-web-test.py" --host "$HOST" --port "$PORT" &
  SERVER_PID="$!"
  sleep 0.6
  if ! kill -0 "$SERVER_PID" >/dev/null 2>&1; then
    wait "$SERVER_PID" || true
    cat >&2 <<EOF
本地测试服务启动失败: ${HOST}:${PORT}

如果端口被占用，可以换一个端口：
  MYTHE_DISPLAY_PORT=4174 scripts/run-kiosk-web-test.sh
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
  exec dbus-run-session -- cage -s -- env MOZ_ENABLE_WAYLAND=1 "$BROWSER" --kiosk "$URL"
fi

USER_DATA_DIR="${MYTHE_DISPLAY_BROWSER_PROFILE:-/tmp/mythe-display-kiosk-profile}"
mkdir -p "$USER_DATA_DIR"

exec dbus-run-session -- cage -s -- "$BROWSER" \
  --kiosk "$URL" \
  --user-data-dir="$USER_DATA_DIR" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-features=Translate \
  --proxy-bypass-list="<-loopback>" \
  --ozone-platform=wayland
