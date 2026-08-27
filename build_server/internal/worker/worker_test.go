package worker

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

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

func TestPackerDiagnosticScorePrefersActionableFailure(t *testing.T) {
	serviceFailure := "Job for nginx.service failed because the control process exited"
	pluginNoise := "failed to unlock port lockfile"
	if packerDiagnosticScore(serviceFailure) <= packerDiagnosticScore(pluginNoise) {
		t.Fatal("service failure should outrank plugin cleanup noise")
	}
	if packerDiagnosticScore("Error: Unable to locate package tomcat9") <= packerDiagnosticScore(serviceFailure) {
		t.Fatal("missing package should be the most actionable diagnostic")
	}
}
