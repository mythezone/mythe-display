#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="mythe-display-kiosk.service"
UNIT_SOURCE="$ROOT_DIR/systemd/$UNIT_NAME"
UNIT_TARGET="/etc/systemd/system/$UNIT_NAME"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  cat >&2 <<EOF
请使用 sudo 安装 systemd 服务：
  sudo scripts/install-kiosk-service.sh
EOF
  exit 1
fi

if [[ ! -f "$UNIT_SOURCE" ]]; then
  echo "找不到服务模板: $UNIT_SOURCE" >&2
  exit 1
fi

install -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
systemctl daemon-reload

cat <<EOF
已安装 $UNIT_NAME

立即启动:
  sudo systemctl start $UNIT_NAME

查看日志:
  journalctl -u $UNIT_NAME -f

刷新当前界面，不重启服务:
  sudo systemctl reload $UNIT_NAME
  scripts/kiosk-control.py reload

动态切换当前界面:
  scripts/kiosk-control.py switch /kiosk-test/
  scripts/kiosk-control.py switch https://example.com

设置开机自启:
  sudo systemctl enable $UNIT_NAME

停止:
  sudo systemctl stop $UNIT_NAME
EOF
