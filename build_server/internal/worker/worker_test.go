package worker

import (
	"errors"
	"os"
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
	passwordIndex := strings.Index(text, `ubuntu '${var.machine_password}' | chpasswd`)
	if buildIndex < 0 || passwordIndex < 0 || passwordIndex <= buildIndex {
		t.Fatal("Packer must change the ubuntu password after build.sh succeeds")
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
	if got := artifactType("image.qcow2"); got != "qcow2" {
		t.Fatalf("artifactType() = %q, want qcow2", got)
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
