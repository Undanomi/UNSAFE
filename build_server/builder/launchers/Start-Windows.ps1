[CmdletBinding()]
param(
    [string]$ImagePath = (Join-Path $PSScriptRoot "image.qcow2"),
    [ValidateRange(512, 1048576)]
    [int]$MemoryMB = 4096,
    [ValidateRange(1, 256)]
    [int]$CPUs = 2,
    [string]$TapAdapter = "OpenVPN TAP-Windows6",
    [ValidateSet("whpx", "tcg")]
    [string]$Accelerator = "whpx"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "qcow2 image not found: $ImagePath"
}
$ImagePath = (Resolve-Path -LiteralPath $ImagePath).Path

$qemu = Get-Command "qemu-system-x86_64.exe" -ErrorAction SilentlyContinue
if (-not $qemu) {
    $qemu = Get-Command "qemu-system-x86_64" -ErrorAction SilentlyContinue
}
if (-not $qemu) {
    throw "qemu-system-x86_64 is not installed or is not in PATH."
}

$accelValue = if ($Accelerator -eq "whpx") { "whpx" } else { "tcg,thread=multi" }
$cpuModel = if ($Accelerator -eq "whpx") { "qemu64" } else { "max" }

$qemuArgs = @(
    "-name", "SLSG-target",
    "-machine", "q35",
    "-accel", $accelValue,
    "-cpu", $cpuModel,
    "-m", $MemoryMB.ToString(),
    "-smp", $CPUs.ToString(),
    "-boot", "order=c",
    "-drive", "file=$ImagePath,format=qcow2,if=virtio"
)

$qemuArgs += @(
    "-netdev", "tap,id=net0,ifname=$TapAdapter",
    "-device", "virtio-net-pci,netdev=net0"
)
Write-Host "Network: TAP $TapAdapter (use the IPv4 address shown on the guest console)"

& $qemu.Source @qemuArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0 -and $Accelerator -eq "whpx") {
    Write-Warning "QEMU failed with WHPX. Enable Windows Hypervisor Platform or retry with -Accelerator tcg."
}
exit $exitCode
