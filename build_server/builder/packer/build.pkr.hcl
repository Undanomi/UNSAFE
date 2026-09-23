packer {
  required_plugins {
    qemu = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "base_image" {
  type    = string
  default = "/opt/slsg/base_images/debian-13.7.0-amd64.qcow2"
}

variable "source_dir" {
  type        = string
  description = "Absolute path to the validated scenario source copied into the build workspace."
}

variable "output_dir" {
  type        = string
  description = "Temporary output directory. The worker publishes it atomically after validation."
}

variable "machine_password" {
  type        = string
  description = "Random password assigned to the provisioner user after scenario provisioning."
  sensitive   = true
}

source "qemu" "debian1370_result" {
  accelerator      = "kvm"
  cpus             = 4
  disk_compression = true
  disk_image       = true
  format           = "qcow2"
  headless         = true
  iso_checksum     = "none"
  iso_url          = var.base_image
  machine_type     = "q35"
  memory           = 4096
  net_device       = "virtio-net-pci"
  output_directory = var.output_dir
  shutdown_command = "echo '${var.machine_password}' | sudo -S shutdown -P now"
  ssh_password     = "provisioner"
  ssh_timeout      = "15m"
  ssh_username     = "provisioner"
  vm_name          = "image.qcow2"
}

build {
  name    = "security-scenario"
  sources = ["source.qemu.debian1370_result"]

  provisioner "file" {
    source      = var.source_dir
    destination = "/tmp/scenario"
  }

  provisioner "file" {
    source      = "${path.root}/scripts/configure-login-ip.sh"
    destination = "/tmp/slsg-configure-login-ip.sh"
  }

  provisioner "shell" {
    execute_command = "echo 'provisioner' | sudo -S bash '{{ .Path }}'"
    inline = [
      "set -e",
      "BUILD_SH=/tmp/scenario/contents/build.sh",
      "if [ ! -f \"$BUILD_SH\" ]; then BUILD_SH=/tmp/scenario/build.sh; fi",
      "if [ ! -f \"$BUILD_SH\" ]; then BUILD_SH=$(find /tmp/scenario -mindepth 1 -maxdepth 3 -type f -name build.sh | head -n 1); fi",
      "test -n \"$BUILD_SH\" || { echo 'missing build.sh in scenario source'; exit 1; }",
      "chmod +x \"$BUILD_SH\"",
      "cd \"$(dirname \"$BUILD_SH\")\"",
      "find . -type f -name '*.sh' -exec chmod +x {} \\;",
      "./build.sh",
      "test -f ./scripts/verify.sh || { echo 'missing scripts/verify.sh in scenario source'; exit 1; }",
      "./scripts/verify.sh",
      "bash /tmp/slsg-configure-login-ip.sh",
      "rm -f /tmp/slsg-configure-login-ip.sh",
      "printf '%s:%s\\n' provisioner '${var.machine_password}' | chpasswd",
    ]
  }
}
