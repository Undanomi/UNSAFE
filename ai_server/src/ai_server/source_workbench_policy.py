from __future__ import annotations

from pathlib import PurePosixPath

TARGET_VM_EXECUTABLES = frozenset(
    {
        "hostnamectl",
        "journalctl",
        "localectl",
        "loginctl",
        "machinectl",
        "mount",
        "networkctl",
        "packer",
        "qemu-system-x86_64",
        "reboot",
        "service",
        "systemctl",
        "systemd-analyze",
        "systemd-run",
        "timedatectl",
        "udevadm",
        "umount",
    }
)


def is_target_vm_executable(raw: str) -> bool:
    return PurePosixPath(raw).name in TARGET_VM_EXECUTABLES
