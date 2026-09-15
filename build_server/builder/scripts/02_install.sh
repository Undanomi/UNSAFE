#!/bin/bash

qemu-system-x86_64 \
  -enable-kvm \
  -m 4096 \
  -smp 2 \
  -cpu host \
  -drive file=../base_images/debian-13.7.0-amd64.qcow2,format=qcow2,if=virtio \
  -cdrom ../iso/debian-13.7.0-amd64-netinst.iso \
  -boot d \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-pci,netdev=net0