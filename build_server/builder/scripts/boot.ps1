qemu-system-x86_64 `
  -accel 'tcg,thread=multi' `
  -m 4096 `
  -smp 2 `
  -cpu max `
  -machine q35 `
  -boot order=c `
  -drive file=../base_images/debian-13.7.0-amd64.qcow2,format=qcow2,if=virtio `
  -netdev 'tap,id=net0,ifname=OpenVPN TAP-Windows6' `
  -device virtio-net-pci,netdev=net0