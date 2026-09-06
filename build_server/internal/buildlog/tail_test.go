package buildlog

import (
	"os"
	"path/filepath"
	"testing"
)

func TestTailKeepsRecentMultilineContext(t *testing.T) {
	path := filepath.Join(t.TempDir(), "packer.log")
	content := "old context\ncommand before failure\nerror detail line 1\nerror detail line 2\n"
	if err := os.WriteFile(path, []byte(content), 0o640); err != nil {
		t.Fatal(err)
	}
	got, err := Tail(path, 1<<10, 3)
	if err != nil {
		t.Fatal(err)
	}
	want := "command before failure\nerror detail line 1\nerror detail line 2"
	if got != want {
		t.Fatalf("Tail() = %q, want %q", got, want)
	}
}
