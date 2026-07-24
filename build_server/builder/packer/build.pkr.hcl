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
  default = "/opt/slsg/base_images/ubuntu-26.04-server.qcow2"
}

variable "source_dir" {
  type        = string
  description = "Absolute path to the validated scenario source copied into the build workspace."
}

variable "output_dir" {
  type        = string
  description = "Temporary output directory. The worker publishes it atomically after validation."
}

source "qemu" "ubuntu2604_result" {
  accelerator      = "kvm"
  cpus             = 4
  disk_compression = true
  disk_image       = true
  format           = "qcow2"
  headless         = true
  iso_checksum     = "none"
  iso_url          = var.base_image
  memory           = 4096
  net_device       = "virtio-net"
  output_directory = var.output_dir
  shutdown_command = "echo 'ubuntu' | sudo -S shutdown -P now"
  ssh_password     = "ubuntu"
  ssh_timeout      = "15m"
  ssh_username     = "ubuntu"
  vm_name          = "image.qcow2"
}

build {
  name    = "security-scenario"
  sources = ["source.qemu.ubuntu2604_result"]

  provisioner "file" {
    source      = var.source_dir
    destination = "/tmp/scenario"
  }

  provisioner "shell" {
    execute_command = "echo 'ubuntu' | sudo -S bash '{{ .Path }}'"
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
    ]
  }
}
