#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
image_path="$script_dir/image.qcow2"
memory_mb=4096
cpus=2
bridge_interface=""

usage() {
  cat <<'USAGE'
Usage: ./start-macos.sh [options]

Options:
  --image PATH             qcow2 image (default: image.qcow2 beside this script)
  --memory MB              guest memory in MiB (default: 4096)
  --cpus COUNT             virtual CPU count (default: 2)
  --bridge INTERFACE       vmnet bridge (required; for example, en0)
  -h, --help               show this help

Examples:
  ./start-macos.sh --bridge en0
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
    --bridge)
      (($# >= 2)) || { echo "--bridge requires a value" >&2; exit 2; }
      bridge_interface=$2
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
  echo "qemu-system-x86_64 is not installed. Install QEMU with: brew install qemu" >&2
  exit 1
}

[[ -n $bridge_interface ]] || {
  echo "A deliberately isolated bridge interface is required. Specify it with --bridge." >&2
  exit 1
}

if [[ $(uname -m) == x86_64 ]]; then
  accelerator="hvf"
  cpu_model="host"
else
  accelerator="tcg,thread=multi"
  cpu_model="max"
  echo "Apple Silicon detected; emulating the x86_64 CPU with TCG." >&2
fi

echo "Network: vmnet bridge $bridge_interface (use the IPv4 address shown on the guest console)"

exec qemu-system-x86_64 \
  -name SLSG-target \
  -machine q35 \
  -accel "$accelerator" \
  -cpu "$cpu_model" \
  -m "$memory_mb" \
  -smp "$cpus" \
  -boot order=c \
  -display cocoa \
  -drive "file=$image_path,format=qcow2,if=virtio" \
  -netdev "vmnet-bridged,id=net0,ifname=$bridge_interface" \
  -device virtio-net-pci,netdev=net0
