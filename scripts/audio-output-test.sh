#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  scripts/audio-output-test.sh [alsa-device] [duration-seconds] [frequency-hz]

Examples:
  scripts/audio-output-test.sh
  scripts/audio-output-test.sh plughw:0,3 3 880
  scripts/audio-output-test.sh hw:0,0 3 440
EOF
  exit 0
fi

DEVICE="${1:-${MYTHE_DISPLAY_ALSA_OUTPUT_DEVICE:-plughw:0,3}}"
DURATION="${2:-3}"
FREQUENCY="${3:-880}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ffmpeg 未安装，无法生成 ALSA 测试音。
请先安装 ffmpeg，或使用系统的 alsa-utils/speaker-test。
EOF
  exit 1
fi

echo "输出 ALSA 测试音: device=${DEVICE}, duration=${DURATION}s, frequency=${FREQUENCY}Hz"
exec ffmpeg \
  -hide_banner \
  -loglevel warning \
  -nostdin \
  -f lavfi \
  -i "sine=frequency=${FREQUENCY}:duration=${DURATION}" \
  -ac 2 \
  -ar 48000 \
  -f alsa \
  "$DEVICE"
