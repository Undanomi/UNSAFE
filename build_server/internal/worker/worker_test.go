package worker

import (
	"archive/zip"
	"context"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestNewMachinePassword(t *testing.T) {
	first, err := newMachinePassword()
	if err != nil {
		t.Fatal(err)
	}
	second, err := newMachinePassword()
	if err != nil {
		t.Fatal(err)
	}
	if !regexp.MustCompile(`^[A-Za-z0-9_-]{32}$`).MatchString(first) {
		t.Fatalf("newMachinePassword() = %q, want 32 URL-safe characters", first)
	}
	if first == second {
		t.Fatal("newMachinePassword() returned the same value twice")
	}
}

func TestDriveConversionUpdate(t *testing.T) {
	tests := []struct {
		name         string
		line         string
		wantProgress int
		wantMessage  string
		wantMatched  bool
	}{
		{
			name:         "packer conversion output",
			line:         "==> security-scenario.qemu.debian1370_result: Converting hard drive...",
			wantProgress: 80,
			wantMessage:  "converting hard drive image",
			wantMatched:  true,
		},
		{
			name:        "unrelated packer output",
			line:        "==> security-scenario.qemu.debian1370_result: Gracefully halting virtual machine...",
			wantMatched: false,
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			progress, message, matched := driveConversionUpdate(test.line)
			if progress != test.wantProgress || message != test.wantMessage || matched != test.wantMatched {
				t.Fatalf(
					"driveConversionUpdate(%q) = (%d, %q, %t), want (%d, %q, %t)",
					test.line,
					progress,
					message,
					matched,
					test.wantProgress,
					test.wantMessage,
					test.wantMatched,
				)
			}
		})
	}
}

func TestPackerChangesProvisionerPasswordAfterScenarioBuild(t *testing.T) {
	template, err := os.ReadFile("../../builder/packer/build.pkr.hcl")
	if err != nil {
		t.Fatal(err)
	}
	text := string(template)
	buildIndex := strings.Index(text, `"bash ./build.sh"`)
	flagsIndex := strings.Index(text, `"bash ./scripts/install-flags.sh"`)
	verifyIndex := strings.Index(text, `"bash ./scripts/verify.sh"`)
	cleanupIndex := strings.Index(text, `"rm -rf /tmp/scenario"`)
	bannerIndex := strings.Index(text, `"bash /tmp/slsg-configure-login-ip.sh"`)
	passwordIndex := strings.Index(text, `provisioner '${var.machine_password}' | chpasswd`)
	if buildIndex < 0 || flagsIndex <= buildIndex || verifyIndex <= flagsIndex || cleanupIndex <= verifyIndex || bannerIndex <= cleanupIndex || passwordIndex <= bannerIndex {
		t.Fatal("Packer must verify the scenario before configuring login and changing the password")
	}
	for _, required := range []string{
		`variable "machine_password"`,
		`sensitive   = true`,
		`shutdown_command = "echo '${var.machine_password}' | sudo -S shutdown -P now"`,
		`destination = "/tmp/slsg-bash-env.sh"`,
		`"export SLSG_PHASE=provision"`,
		`"export SLSG_PHASE=verification"`,
	} {
		if !strings.Contains(text, required) {
			t.Fatalf("Packer template is missing %q", required)
		}
	}
}

func TestPackerNetworkDeviceMatchesBootScript(t *testing.T) {
	packerTemplate, err := os.ReadFile("../../builder/packer/build.pkr.hcl")
	if err != nil {
		t.Fatal(err)
	}
	bootScript, err := os.ReadFile("../../builder/scripts/boot.sh")
	if err != nil {
		t.Fatal(err)
	}

	for _, required := range []string{
		`machine_type     = "q35"`,
		`net_device       = "virtio-net-pci"`,
	} {
		if !strings.Contains(string(packerTemplate), required) {
			t.Fatalf("Packer template is missing boot-compatible setting %q", required)
		}
	}
	for _, required := range []string{
		`-machine q35`,
		`-netdev user,id=net0,hostfwd=tcp::2222-:22`,
		`-device virtio-net-pci,netdev=net0`,
	} {
		if !strings.Contains(string(bootScript), required) {
			t.Fatalf("boot.sh is missing expected network setting %q", required)
		}
	}
}

func TestCopyTreeRejectsSymlink(t *testing.T) {
	source := t.TempDir()
	destination := filepath.Join(t.TempDir(), "copy")
	if err := os.Symlink("/etc/passwd", filepath.Join(source, "escape")); err != nil {
		t.Fatal(err)
	}
	err := copyTree(source, destination)
	if err == nil || !strings.Contains(err.Error(), "symbolic links") {
		t.Fatalf("copyTree() error = %v, want symbolic-link rejection", err)
	}
}

func TestArtifactType(t *testing.T) {
	if got := artifactType("3a3c16bd-6d41-49e1-98c3-927138f8a271.zip"); got != "zip" {
		t.Fatalf("artifactType() = %q, want zip", got)
	}
	if got := artifactType("start-linux.sh"); got != "launcher" {
		t.Fatalf("artifactType() = %q, want launcher", got)
	}
	if got := artifactType("README-Linux.md"); got != "documentation" {
		t.Fatalf("artifactType() = %q, want documentation", got)
	}
}

func TestPackageArtifactsCreatesSingleZip(t *testing.T) {
	source := t.TempDir()
	work := t.TempDir()
	artifactID := "3a3c16bd-6d41-49e1-98c3-927138f8a271"
	archiveName := distributionFileName(artifactID)
	files := map[string]string{
		"image.qcow2":     "disk",
		"start-linux.sh":  "#!/bin/sh\n",
		"README-Linux.md": "# Linux\n",
	}
	for name, contents := range files {
		if err := os.WriteFile(filepath.Join(source, name), []byte(contents), 0o640); err != nil {
			t.Fatal(err)
		}
	}
	if err := packageArtifacts(context.Background(), source, work, archiveName); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(source)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != archiveName {
		t.Fatalf("packaged entries = %v, want only %s", entries, archiveName)
	}
	archive, err := zip.OpenReader(filepath.Join(source, archiveName))
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	archived := make(map[string]string, len(archive.File))
	for _, file := range archive.File {
		input, err := file.Open()
		if err != nil {
			t.Fatal(err)
		}
		contents, readErr := io.ReadAll(input)
		closeErr := input.Close()
		if readErr != nil {
			t.Fatal(readErr)
		}
		if closeErr != nil {
			t.Fatal(closeErr)
		}
		archived[file.Name] = string(contents)
	}
	if len(archived) != len(files) {
		t.Fatalf("archive entries = %v, want %d files", archived, len(files))
	}
	for name, contents := range files {
		archiveName := "slsg-machine/" + name
		if archived[archiveName] != contents {
			t.Fatalf("archive entry %q = %q, want %q", archiveName, archived[archiveName], contents)
		}
	}
}

func TestDistributionFileNameUsesArtifactID(t *testing.T) {
	artifactID := "3a3c16bd-6d41-49e1-98c3-927138f8a271"
	if got := distributionFileName(artifactID); got != artifactID+".zip" {
		t.Fatalf("distributionFileName() = %q, want %q", got, artifactID+".zip")
	}
}

func TestConvertLegacyTarZstCreatesArtifactIDZip(t *testing.T) {
	if _, err := exec.LookPath("tar"); err != nil {
		t.Skip("tar is not installed")
	}
	if _, err := exec.LookPath("zstd"); err != nil {
		t.Skip("zstd is not installed")
	}
	root := t.TempDir()
	machineDir := filepath.Join(root, "slsg-machine")
	if err := os.Mkdir(machineDir, 0o750); err != nil {
		t.Fatal(err)
	}
	files := map[string]string{
		"image.qcow2":     "legacy disk",
		"start-linux.sh":  "#!/bin/sh\n",
		"README-Linux.md": "# Linux\n",
	}
	for name, contents := range files {
		if err := os.WriteFile(filepath.Join(machineDir, name), []byte(contents), 0o640); err != nil {
			t.Fatal(err)
		}
	}
	legacyPath := filepath.Join(root, "slsg-machine.tar.zst")
	command := exec.Command("tar", "--zstd", "-cf", legacyPath, "-C", root, "slsg-machine")
	if output, err := command.CombinedOutput(); err != nil {
		t.Fatalf("create legacy archive: %v: %s", err, output)
	}
	artifactID := "3a3c16bd-6d41-49e1-98c3-927138f8a271"
	zipPath := filepath.Join(root, distributionFileName(artifactID))
	if err := convertLegacyTarZst(context.Background(), legacyPath, zipPath); err != nil {
		t.Fatal(err)
	}
	if err := validateDistributionZip(zipPath); err != nil {
		t.Fatal(err)
	}
	archive, err := zip.OpenReader(zipPath)
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	if len(archive.File) != len(files) {
		t.Fatalf("zip contains %d files, want %d", len(archive.File), len(files))
	}
	for _, file := range archive.File {
		name := strings.TrimPrefix(file.Name, "slsg-machine/")
		if _, ok := files[name]; !ok {
			t.Fatalf("unexpected zip entry %q", file.Name)
		}
	}
}

func TestCopyLauncherAssetsCopiesFlatFiles(t *testing.T) {
	source := t.TempDir()
	destination := t.TempDir()
	if err := os.WriteFile(filepath.Join(source, "start-linux.sh"), []byte("#!/bin/sh\n"), 0o750); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(source, "README-Linux.md"), []byte("# Linux\n"), 0o640); err != nil {
		t.Fatal(err)
	}
	if err := copyLauncherAssets(source, destination); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"start-linux.sh", "README-Linux.md"} {
		if _, err := os.Stat(filepath.Join(destination, name)); err != nil {
			t.Fatalf("copied asset %q: %v", name, err)
		}
	}
}

func TestCopyLauncherAssetsRejectsDirectory(t *testing.T) {
	source := t.TempDir()
	if err := os.Mkdir(filepath.Join(source, "nested"), 0o750); err != nil {
		t.Fatal(err)
	}
	err := copyLauncherAssets(source, t.TempDir())
	if err == nil || !strings.Contains(err.Error(), "unsupported entry") {
		t.Fatalf("copyLauncherAssets() error = %v, want unsupported-entry rejection", err)
	}
}

func TestResolveBaseImageUsesManifestTargetOS(t *testing.T) {
	source := t.TempDir()
	baseImages := t.TempDir()
	if err := os.MkdirAll(filepath.Join(source, "contents"), 0o750); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(source, "contents", "scenario_manifest.json"),
		[]byte(`{"target_os":"Debian 12.11.0"}`),
		0o640,
	); err != nil {
		t.Fatal(err)
	}
	want := filepath.Join(baseImages, "debian-12.11.0-amd64.qcow2")
	if err := os.WriteFile(want, []byte("image"), 0o640); err != nil {
		t.Fatal(err)
	}
	got, err := resolveBaseImage(source, baseImages)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("resolveBaseImage() = %q, want %q", got, want)
	}
}

func TestResolveBaseImageDefaultsToDebian1370(t *testing.T) {
	source := t.TempDir()
	baseImages := t.TempDir()
	if err := os.MkdirAll(filepath.Join(source, "contents"), 0o750); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		filepath.Join(source, "contents", "scenario_manifest.json"),
		[]byte(`{}`),
		0o640,
	); err != nil {
		t.Fatal(err)
	}
	want := filepath.Join(baseImages, "debian-13.7.0-amd64.qcow2")
	if err := os.WriteFile(want, []byte("image"), 0o640); err != nil {
		t.Fatal(err)
	}
	got, err := resolveBaseImage(source, baseImages)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("resolveBaseImage() = %q, want %q", got, want)
	}
}

func TestSanitizeErrorPreservesMultilineContext(t *testing.T) {
	got := sanitizeError(errors.New("build failed\ncommand context\nerror detail"))
	if got != "build failed\ncommand context\nerror detail" {
		t.Fatalf("sanitizeError() = %q", got)
	}
}
