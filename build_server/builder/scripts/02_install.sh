#!/bin/bash

qemu-system-x86_64 \
  -enable-kvm \
  -m 4096 \
  -smp 2 \
  -cpu host \
  -drive file=../base_images/ubuntu-26.04-server.qcow2,format=qcow2,if=virtio \
  -cdrom ../iso/ubuntu-26.04-live-server-amd64.iso \
  -boot d \
  -netdev user,id=net0,hostfwd=tcp::2222-:22 \
  -device virtio-net-pci,netdev=net0