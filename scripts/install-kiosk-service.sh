#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="mythe-display-kiosk.service"
UNIT_SOURCE="$ROOT_DIR/systemd/$UNIT_NAME"
UNIT_TARGET="/etc/systemd/system/$UNIT_NAME"
MDP_SOURCE="$ROOT_DIR/scripts/mdp"
MDP_TARGET="/usr/bin/mdp"

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
if [[ -f "$MDP_SOURCE" ]]; then
  chmod 0755 "$MDP_SOURCE"
  ln -sfn "$MDP_SOURCE" "$MDP_TARGET"
fi
systemctl daemon-reload

cat <<EOF
已安装 $UNIT_NAME
已安装 $MDP_TARGET

立即启动:
  mdp start

查看日志:
  mdp logs

刷新当前界面，不重启服务:
  mdp reload

动态切换当前界面:
  mdp switch /kiosk-test/
  mdp switch https://example.com

设置开机自启:
  mdp enable

停止:
  mdp stop
EOF
