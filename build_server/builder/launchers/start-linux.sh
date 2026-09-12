#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
image_path="$script_dir/image.qcow2"
memory_mb=4096
cpus=2
tap_interface="tap-slsg"

usage() {
  cat <<'USAGE'
Usage: ./start-linux.sh [options]

Options:
  --image PATH             qcow2 image (default: image.qcow2 beside this script)
  --memory MB              guest memory in MiB (default: 4096)
  --cpus COUNT             virtual CPU count (default: 2)
  --tap INTERFACE          existing TAP interface (default: tap-slsg)
  -h, --help               show this help

Examples:
  ./start-linux.sh
  ./start-linux.sh --tap tap-scenario-1
USAGE
}

while (($#)); do
  case "$1" in
    --image)
      (($# >= 2)) || { echo "--image requires a value" >&2; exit 2; }
      image_path=$2
      shift 2
      ;;
    --memory)
      (($# >= 2)) || { echo "--memory requires a value" >&2; exit 2; }
      memory_mb=$2
      shift 2
      ;;
    --cpus)
      (($# >= 2)) || { echo "--cpus requires a value" >&2; exit 2; }
      cpus=$2
      shift 2
      ;;
    --tap)
      (($# >= 2)) || { echo "--tap requires a value" >&2; exit 2; }
      tap_interface=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for value in "$memory_mb" "$cpus"; do
  [[ $value =~ ^[0-9]+$ ]] || { echo "Numeric option has an invalid value: $value" >&2; exit 2; }
done

[[ -f $image_path ]] || { echo "qcow2 image not found: $image_path" >&2; exit 1; }
command -v qemu-system-x86_64 >/dev/null 2>&1 || {
  echo "qemu-system-x86_64 is not installed or is not in PATH." >&2
  exit 1
}
command -v ip >/dev/null 2>&1 || {
  echo "The ip command is required to validate the TAP interface." >&2
  exit 1
}
ip link show dev "$tap_interface" >/dev/null 2>&1 || {
  echo "TAP interface '$tap_interface' does not exist. See README-Linux.md." >&2
  exit 1
}

if [[ $(uname -m) == x86_64 && -r /dev/kvm && -w /dev/kvm ]]; then
  accelerator="kvm"
  cpu_model="host"
else
  accelerator="tcg,thread=multi"
  cpu_model="max"
  echo "KVM is unavailable; using the slower TCG x86_64 emulator." >&2
fi

echo "Network: TAP $tap_interface (use the IPv4 address shown on the guest console)"

exec qemu-system-x86_64 \
  -name SLSG-target \
  -machine q35 \
  -accel "$accelerator" \
  -cpu "$cpu_model" \
  -m "$memory_mb" \
  -smp "$cpus" \
  -boot order=c \
  -drive "file=$image_path,format=qcow2,if=virtio" \
  -netdev "tap,id=net0,ifname=$tap_interface,script=no,downscript=no" \
  -device virtio-net-pci,netdev=net0
