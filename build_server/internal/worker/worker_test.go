package worker

import (
	"context"
	"errors"
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

func TestPackerChangesUbuntuPasswordAfterScenarioBuild(t *testing.T) {
	template, err := os.ReadFile("../../builder/packer/build.pkr.hcl")
	if err != nil {
		t.Fatal(err)
	}
	text := string(template)
	buildIndex := strings.Index(text, `"./build.sh"`)
	bannerIndex := strings.Index(text, `"bash /tmp/slsg-configure-login-ip.sh"`)
	passwordIndex := strings.Index(text, `ubuntu '${var.machine_password}' | chpasswd`)
	if buildIndex < 0 || bannerIndex <= buildIndex || passwordIndex <= bannerIndex {
		t.Fatal("Packer must configure the login banner and change the password after build.sh succeeds")
	}
	for _, required := range []string{
		`variable "machine_password"`,
		`sensitive   = true`,
		`shutdown_command = "echo '${var.machine_password}' | sudo -S shutdown -P now"`,
	} {
		if !strings.Contains(text, required) {
			t.Fatalf("Packer template is missing %q", required)
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
	if got := artifactType("slsg-machine.tar.zst"); got != "tar.zst" {
		t.Fatalf("artifactType() = %q, want tar.zst", got)
	}
	if got := artifactType("start-linux.sh"); got != "launcher" {
		t.Fatalf("artifactType() = %q, want launcher", got)
	}
	if got := artifactType("README-Linux.md"); got != "documentation" {
		t.Fatalf("artifactType() = %q, want documentation", got)
	}
}

func TestPackageArtifactsCreatesSingleTarZst(t *testing.T) {
	if _, err := exec.LookPath("tar"); err != nil {
		t.Skip("tar is not installed")
	}
	if _, err := exec.LookPath("zstd"); err != nil {
		t.Skip("zstd is not installed")
	}
	source := t.TempDir()
	work := t.TempDir()
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
	if err := packageArtifacts(context.Background(), source, work); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(source)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0].Name() != distributionFileName {
		t.Fatalf("packaged entries = %v, want only %s", entries, distributionFileName)
	}
	command := exec.Command("tar", "--zstd", "-tf", filepath.Join(source, distributionFileName))
	output, err := command.Output()
	if err != nil {
		t.Fatal(err)
	}
	for name := range files {
		if !strings.Contains(string(output), "slsg-machine/"+name+"\n") {
			t.Fatalf("archive listing does not contain %q: %s", name, output)
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
		[]byte(`{"target_os":"Ubuntu 24.04 LTS"}`),
		0o640,
	); err != nil {
		t.Fatal(err)
	}
	want := filepath.Join(baseImages, "ubuntu-24.04-server.qcow2")
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

func TestResolveBaseImageDefaultsToUbuntu2604(t *testing.T) {
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
	want := filepath.Join(baseImages, "ubuntu-26.04-server.qcow2")
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
