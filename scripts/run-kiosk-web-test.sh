#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/scripts/load-env.sh" ]]; then
  # shellcheck source=scripts/load-env.sh
  source "$ROOT_DIR/scripts/load-env.sh"
  load_mythe_display_env_defaults "$ROOT_DIR/.env"
fi

PORT="${MYTHE_DISPLAY_PORT:-23456}"
HOST="${MYTHE_DISPLAY_HOST:-127.0.0.1}"
REMOTE_DEBUG_PORT="${MYTHE_DISPLAY_REMOTE_DEBUG_PORT:-23458}"
ALSA_OUTPUT_DEVICE="${MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE:-plughw:0,3}"
DEFAULT_URL="http://${HOST}:${PORT}/kiosk-test/"
URL="${1:-$DEFAULT_URL}"
KIOSK_URL="$URL"
SERVER_PID=""
KIOSK_PID=""
RUNTIME_COLLECTOR_PID=""
FAIO_AUDIO_PLAYER_PID=""
IS_ROOT=0

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

远程 NAS 推荐:
  sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh

运行后动态切换页面:
  scripts/kiosk-control.py list
  scripts/kiosk-control.py switch /kiosk-test/
  scripts/kiosk-control.py reload
  该能力依赖 Chromium DevTools 控制端口，Firefox kiosk 暂不支持。

默认本地测试页会启动低频运行时采集器，生成:
  public/runtime/disks.json       默认 12 小时刷新
  public/runtime/telemetry.json   默认 10 分钟刷新
  public/runtime/docker.json      默认 10 分钟刷新
  public/runtime/weather-shenzhen.json 默认 30 分钟刷新
  public/runtime/codex-agents.json 默认 5 分钟刷新
  public/runtime/faio-listen.json 默认 10 秒刷新

可用 MYTHE_DISPLAY_DISABLE_RUNTIME_COLLECTOR=1 禁用采集器。
可用 MYTHE_DISPLAY_DISABLE_FAIO_LISTEN=1 禁用 FAIO 一起听歌采集。
默认本地测试页会启动 FFmpeg/ALSA 音频播放器，直接输出到 MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE。
可用 MYTHE_DISPLAY_DISABLE_FAIO_AUDIO_PLAYER=1 禁用独立音频播放器。
默认本地测试页启动时会追加 assetCacheBust，避免 Chromium profile 恢复旧 HTML；
可用 MYTHE_DISPLAY_START_CACHE_BUST=0 关闭。
EOF
  exit 0
fi

cleanup() {
  if [[ -n "$FAIO_AUDIO_PLAYER_PID" ]]; then
    kill "$FAIO_AUDIO_PLAYER_PID" >/dev/null 2>&1 || true
    wait "$FAIO_AUDIO_PLAYER_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$RUNTIME_COLLECTOR_PID" ]]; then
    kill "$RUNTIME_COLLECTOR_PID" >/dev/null 2>&1 || true
    wait "$RUNTIME_COLLECTOR_PID" >/dev/null 2>&1 || true
  fi
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

append_query_param() {
  local url="$1"
  local key="$2"
  local value="$3"
  local sep="?"
  if [[ "$url" == *"?"* ]]; then
    sep="&"
  fi
  printf '%s%s%s=%s\n' "$url" "$sep" "$key" "$value"
}

drm_device_has_connected_connector() {
  local device="$1"
  local card="${device##*/}"
  local status_file=""

  for status_file in /sys/class/drm/"$card"-*/status; do
    [[ -e "$status_file" ]] || continue
    if [[ "$(cat "$status_file" 2>/dev/null || true)" == "connected" ]]; then
      return 0
    fi
  done
  return 1
}

resolve_drm_device() {
  local configured="${MYTHE_DISPLAY_DRM_DEVICE:-auto}"
  local status_file=""
  local connector=""
  local card=""
  local device=""

  if [[ "$configured" != "auto" && -e "$configured" ]]; then
    if [[ "${MYTHE_DISPLAY_DRM_DEVICE_STRICT:-0}" == "1" ]] || drm_device_has_connected_connector "$configured"; then
      printf '%s\n' "$configured"
      return 0
    fi
  fi

  for status_file in /sys/class/drm/card*-*/status; do
    [[ -e "$status_file" ]] || continue
    [[ "$(cat "$status_file" 2>/dev/null || true)" == "connected" ]] || continue
    connector="$(basename "$(dirname "$status_file")")"
    card="${connector%%-*}"
    device="/dev/dri/$card"
    if [[ -e "$device" ]]; then
      printf '%s\n' "$device"
      return 0
    fi
  done

  if [[ "$configured" != "auto" ]]; then
    printf '%s\n' "$configured"
  else
    printf '%s\n' "/dev/dri/card0"
  fi
}

fail_environment() {
  cat >&2 <<EOF
$1

无头 NAS 远程启动请使用 sudo direct DRM 模式：
  sudo MYTHE_DISPLAY_PORT=23456 scripts/run-kiosk-web-test.sh

如果是在本机屏幕上的登录 TTY 中运行，可以使用普通用户模式：
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
  IS_ROOT=1
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/0}"
  install -d -m 700 "$XDG_RUNTIME_DIR"
  export LIBSEAT_BACKEND="${LIBSEAT_BACKEND:-builtin}"
  export WLR_BACKENDS="${WLR_BACKENDS:-drm}"
  RESOLVED_DRM_DEVICE="$(resolve_drm_device)"
  export WLR_DRM_DEVICES="${WLR_DRM_DEVICES:-$RESOLVED_DRM_DEVICE}"
  export WLR_LIBINPUT_NO_DEVICES="${WLR_LIBINPUT_NO_DEVICES:-1}"
  if [[ "${MYTHE_DISPLAY_WAIT_FOR_DRM_READY:-1}" == "1" ]]; then
    python3 "$ROOT_DIR/scripts/drm-hotplug-monitor.py" \
      --wait-ready \
      --device "$RESOLVED_DRM_DEVICE" \
      --connector "${MYTHE_DISPLAY_DRM_CONNECTOR:-}" \
      --mode "${MYTHE_DISPLAY_DRM_MODE:-3840x1100}" \
      --poll-ms "${MYTHE_DISPLAY_HOTPLUG_POLL_MS:-1000}" \
      --stable-ms "${MYTHE_DISPLAY_DRM_READY_STABLE_MS:-2000}" \
      --timeout-ms "${MYTHE_DISPLAY_DRM_READY_TIMEOUT_MS:-20000}"
  fi
  if [[ "${MYTHE_DISPLAY_DISABLE_DRM_ATOMIC:-1}" == "1" ]]; then
    export WLR_DRM_NO_ATOMIC="${WLR_DRM_NO_ATOMIC:-1}"
  fi
  if [[ "${MYTHE_DISPLAY_DISABLE_DRM_MODIFIERS:-1}" == "1" ]]; then
    export WLR_DRM_NO_MODIFIERS="${WLR_DRM_NO_MODIFIERS:-1}"
  fi
  echo "以 root/sudo direct DRM 模式启动: LIBSEAT_BACKEND=$LIBSEAT_BACKEND, WLR_DRM_DEVICES=$WLR_DRM_DEVICES, WLR_DRM_NO_ATOMIC=${WLR_DRM_NO_ATOMIC:-0}, WLR_DRM_NO_MODIFIERS=${WLR_DRM_NO_MODIFIERS:-0}" >&2
fi

if [[ "$IS_ROOT" -eq 0 && "${MYTHE_DISPLAY_ALLOW_REMOTE_KIOSK:-0}" != "1" ]]; then
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

if [[ "$IS_ROOT" -eq 0 && "${MYTHE_DISPLAY_SKIP_GROUP_CHECK:-0}" != "1" ]]; then
  user_groups="$(id -nG 2>/dev/null || true)"
  if [[ -z "$user_groups" ]]; then
    fail_environment "无法读取当前用户组。"
  fi
  for required_group in video render input; do
    if [[ " $user_groups " != *" $required_group "* ]]; then
      fail_environment "当前用户组缺少 $required_group。"
    fi
  done
fi

if [[ "$URL" == "$DEFAULT_URL" ]]; then
  if [[ "${MYTHE_DISPLAY_DISABLE_RUNTIME_COLLECTOR:-0}" != "1" ]]; then
    RUNTIME_COLLECTOR_ARGS=(
      --disk-ms "${MYTHE_DISPLAY_DISK_REFRESH_MS:-43200000}"
      --telemetry-ms "${MYTHE_DISPLAY_TELEMETRY_REFRESH_MS:-600000}"
      --docker-ms "${MYTHE_DISPLAY_DOCKER_REFRESH_MS:-600000}"
      --weather-ms "${MYTHE_DISPLAY_WEATHER_REFRESH_MS:-1800000}"
      --agents-ms "${MYTHE_DISPLAY_AGENTS_REFRESH_MS:-300000}"
      --faio-listen-ms "${MYTHE_DISPLAY_FAIO_LISTEN_REFRESH_MS:-10000}"
    )
    if [[ "${MYTHE_DISPLAY_DISABLE_FAIO_LISTEN:-0}" == "1" ]]; then
      RUNTIME_COLLECTOR_ARGS+=(--disable-faio-listen)
    fi
    python3 "$ROOT_DIR/scripts/collect-runtime-snapshots.py" "${RUNTIME_COLLECTOR_ARGS[@]}" --once || true
    python3 "$ROOT_DIR/scripts/collect-runtime-snapshots.py" "${RUNTIME_COLLECTOR_ARGS[@]}" --delay-first &
    RUNTIME_COLLECTOR_PID="$!"
  fi

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

  if [[ "${MYTHE_DISPLAY_DISABLE_FAIO_AUDIO_PLAYER:-0}" != "1" && "${MYTHE_DISPLAY_DISABLE_FAIO_LISTEN:-0}" != "1" ]]; then
    python3 "$ROOT_DIR/scripts/faio-listen-audio-player.py" \
      --snapshot "$ROOT_DIR/public/runtime/faio-listen.json" \
      --base-url "${MYTHE_DISPLAY_FAIO_AUDIO_BASE_URL:-http://127.0.0.1:${PORT}}" \
      --alsa-device "$ALSA_OUTPUT_DEVICE" \
      --poll-ms "${MYTHE_DISPLAY_FAIO_AUDIO_POLL_MS:-2000}" &
    FAIO_AUDIO_PLAYER_PID="$!"
    if [[ "${MYTHE_DISPLAY_FAIO_BROWSER_AUDIO:-0}" != "1" ]]; then
      KIOSK_URL="$(append_query_param "$KIOSK_URL" browserAudio 0)"
    fi
  fi
fi

if [[ "$URL" == "$DEFAULT_URL" && "${MYTHE_DISPLAY_START_CACHE_BUST:-1}" != "0" ]]; then
  KIOSK_URL="$(append_query_param "$KIOSK_URL" faioPublicOutputRefreshMs "${MYTHE_DISPLAY_FAIO_PUBLIC_OUTPUT_REFRESH_MS:-1000}")"
  KIOSK_URL="$(append_query_param "$KIOSK_URL" assetCacheBust "$(date +%s%3N)")"
fi

BROWSER="${MYTHE_DISPLAY_BROWSER:-$(first_command chromium chromium-browser google-chrome firefox firefox-esr || true)}"
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

CAGE_ARGS=()
if [[ "${MYTHE_DISPLAY_ALLOW_VT_SWITCH:-0}" == "1" ]]; then
  CAGE_ARGS+=("-s")
fi

if [[ "$BROWSER" == "firefox" || "$BROWSER" == "firefox-esr" ]]; then
  FIREFOX_ENV=("MOZ_ENABLE_WAYLAND=1")
  dbus-run-session -- cage "${CAGE_ARGS[@]}" -- env "${FIREFOX_ENV[@]}" "$BROWSER" --kiosk "$KIOSK_URL" &
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

CHROMIUM_ARGS=(
  --kiosk "$KIOSK_URL"
  --user-data-dir="$USER_DATA_DIR"
  --noerrdialogs
  --disable-infobars
  --disable-session-crashed-bubble
  --disable-translate
  --disable-features=Translate,TranslateUI,CalculateNativeWinOcclusion
  --disable-background-timer-throttling
  --disable-renderer-backgrounding
  --disable-backgrounding-occluded-windows
  --autoplay-policy=no-user-gesture-required
  --lang=zh-CN
  --accept-lang=zh-CN,zh,en
  --proxy-bypass-list="<-loopback>"
  --ozone-platform=wayland
  --remote-debugging-address=127.0.0.1
  --remote-debugging-port="$REMOTE_DEBUG_PORT"
)

if [[ -n "$ALSA_OUTPUT_DEVICE" ]]; then
  CHROMIUM_ARGS+=(--alsa-output-device="$ALSA_OUTPUT_DEVICE")
fi

if [[ "$IS_ROOT" -eq 1 ]]; then
  CHROMIUM_ARGS+=(--no-sandbox --disable-dev-shm-usage)
fi

dbus-run-session -- cage "${CAGE_ARGS[@]}" -- "$BROWSER" "${CHROMIUM_ARGS[@]}" &
KIOSK_PID="$!"
set +e
wait "$KIOSK_PID"
KIOSK_STATUS="$?"
set -e
KIOSK_PID=""
exit "$KIOSK_STATUS"
