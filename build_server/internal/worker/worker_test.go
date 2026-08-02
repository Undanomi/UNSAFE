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
