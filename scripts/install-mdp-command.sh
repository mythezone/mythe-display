#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT_DIR/scripts/mdp"
TARGET="${MYTHE_DISPLAY_MDP_TARGET:-/usr/bin/mdp}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  cat >&2 <<EOF
请使用 sudo 安装 mdp 命令：
  sudo scripts/install-mdp-command.sh
EOF
  exit 1
fi

if [[ ! -f "$SOURCE" ]]; then
  echo "找不到 mdp 源脚本: $SOURCE" >&2
  exit 1
fi

chmod 0755 "$SOURCE"
ln -sfn "$SOURCE" "$TARGET"

cat <<EOF
已安装 $TARGET -> $SOURCE

常用命令:
  mdp start
  mdp reload
  mdp switch /kiosk-test/
  mdp status
  mdp logs
EOF
