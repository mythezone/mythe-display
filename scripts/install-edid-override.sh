#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEX_SOURCE="$ROOT_DIR/config/edid/mythe-display-3840x1100.hex"
HOOK_SOURCE="$ROOT_DIR/config/initramfs/mythe-display-edid-hook"
FIRMWARE_DIR="/lib/firmware/edid"
FIRMWARE_NAME="mythe-display-3840x1100.bin"
FIRMWARE_TARGET="$FIRMWARE_DIR/$FIRMWARE_NAME"
GRUB_FILE="/etc/default/grub"
HOOK_TARGET="/etc/initramfs-tools/hooks/mythe-display-edid"
KERNEL_ARGS="drm.edid_firmware=HDMI-A-2:edid/$FIRMWARE_NAME video=HDMI-A-2:3840x1100@60e"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "请使用 sudo 运行: sudo scripts/install-edid-override.sh" >&2
  exit 1
fi

if [[ ! -f "$HEX_SOURCE" || ! -f "$HOOK_SOURCE" ]]; then
  echo "找不到 EDID 数据或 initramfs hook。" >&2
  exit 1
fi

install -d -m 0755 "$FIRMWARE_DIR"
xxd -r -p "$HEX_SOURCE" > "$FIRMWARE_TARGET"
chmod 0644 "$FIRMWARE_TARGET"
install -D -m 0755 "$HOOK_SOURCE" "$HOOK_TARGET"
if [[ ! -f "${GRUB_FILE}.mythe-display.bak" ]]; then
  cp -a "$GRUB_FILE" "${GRUB_FILE}.mythe-display.bak"
fi

python3 - "$FIRMWARE_TARGET" "$GRUB_FILE" "$KERNEL_ARGS" <<'PY'
from pathlib import Path
import shlex
import sys

edid_path = Path(sys.argv[1])
grub_path = Path(sys.argv[2])
required_args = sys.argv[3].split()
edid = edid_path.read_bytes()
if len(edid) != 128 or edid[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
    raise SystemExit("EDID 文件格式无效")
if sum(edid) % 256:
    raise SystemExit("EDID checksum 无效")

lines = grub_path.read_text(encoding="utf-8").splitlines()
key = "GRUB_CMDLINE_LINUX_DEFAULT"
updated = False
for index, line in enumerate(lines):
    if not line.startswith(f"{key}="):
        continue
    value = line.split("=", 1)[1].strip()
    current = " ".join(shlex.split(value)) if value else ""
    args = current.split()
    args = [
        arg
        for arg in args
        if not arg.startswith("drm.edid_firmware=")
        and not arg.startswith("video=HDMI-A-2:")
    ]
    args.extend(required_args)
    lines[index] = f'{key}="{" ".join(args)}"'
    updated = True
    break
if not updated:
    lines.append(f'{key}="{" ".join(required_args)}"')
grub_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

update-initramfs -u
update-grub

cat <<EOF
已安装固定 EDID: $FIRMWARE_TARGET
已安装 initramfs hook: $HOOK_TARGET
已配置内核模式: HDMI-A-2 3840x1100@60

需要重启服务器后生效:
  sudo reboot
EOF
