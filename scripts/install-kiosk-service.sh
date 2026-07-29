#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="mythe-display-kiosk.service"
HOTPLUG_UNIT_NAME="mythe-display-hotplug.service"
MDP_SOURCE="$ROOT_DIR/scripts/mdp"
MDP_TARGET="/usr/bin/mdp"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  cat >&2 <<EOF
请使用 sudo 安装 systemd 服务：
  sudo scripts/install-kiosk-service.sh
EOF
  exit 1
fi

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&|]/\\&/g'
}

ROOT_DIR_ESCAPED="$(escape_sed_replacement "$ROOT_DIR")"
for unit_name in "$UNIT_NAME" "$HOTPLUG_UNIT_NAME"; do
  unit_source="$ROOT_DIR/systemd/$unit_name"
  unit_target="/etc/systemd/system/$unit_name"
  if [[ ! -f "$unit_source" ]]; then
    echo "找不到服务模板: $unit_source" >&2
    exit 1
  fi
  sed "s|__MYTHE_DISPLAY_ROOT__|$ROOT_DIR_ESCAPED|g" "$unit_source" > "$unit_target"
  chmod 0644 "$unit_target"
done
if [[ -f "$MDP_SOURCE" ]]; then
  chmod 0755 "$MDP_SOURCE"
  ln -sfn "$MDP_SOURCE" "$MDP_TARGET"
fi
systemctl daemon-reload

if systemctl is-active --quiet "$UNIT_NAME"; then
  cat <<EOF
已更新正在运行的 systemd unit。请执行以下命令使 DRM/hotplug 配置生效：
  mdp restart
EOF
fi

cat <<EOF
已安装 $UNIT_NAME
已安装 $HOTPLUG_UNIT_NAME（由 kiosk 服务自动拉起）
服务路径: $ROOT_DIR
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
