package archive

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestExtractZIP(t *testing.T) {
	body := makeZIP(t, map[string]string{"build.sh": "#!/bin/sh\ntrue\n", "scripts/setup.sh": "true\n"})
	destination := filepath.Join(t.TempDir(), "source")
	if err := ExtractZIP(bytes.NewReader(body), int64(len(body)), destination); err != nil {
		t.Fatal(err)
	}
	content, err := os.ReadFile(filepath.Join(destination, "build.sh"))
	if err != nil {
		t.Fatal(err)
	}
	if string(content) != "#!/bin/sh\ntrue\n" {
		t.Fatalf("unexpected content %q", content)
	}
}

func TestExtractZIPRejectsTraversal(t *testing.T) {
	body := makeZIP(t, map[string]string{"../../escape": "bad"})
	err := ExtractZIP(bytes.NewReader(body), int64(len(body)), filepath.Join(t.TempDir(), "source"))
	if err == nil {
		t.Fatal("ExtractZIP() accepted parent traversal")
	}
}

func TestExtractZIPRejectsSymlink(t *testing.T) {
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	header := &zip.FileHeader{Name: "link", Method: zip.Store}
	header.SetMode(os.ModeSymlink | 0o777)
	entry, err := writer.CreateHeader(header)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = entry.Write([]byte("/etc/passwd"))
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	err = ExtractZIP(bytes.NewReader(buffer.Bytes()), int64(buffer.Len()), filepath.Join(t.TempDir(), "source"))
	if err == nil {
		t.Fatal("ExtractZIP() accepted symbolic link")
	}
}

func TestValidateScenarioSourceRequiresVerificationEntrypoint(t *testing.T) {
	root := t.TempDir()
	for _, name := range requiredScenarioFiles {
		if name == "contents/scripts/verify.sh" {
			continue
		}
		path := filepath.Join(root, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, nil, 0o640); err != nil {
			t.Fatal(err)
		}
	}

	err := ValidateScenarioSource(root)
	if err == nil || !strings.Contains(err.Error(), "contents/scripts/verify.sh") {
		t.Fatalf("ValidateScenarioSource() error = %v, want missing verify.sh", err)
	}
}

func TestValidateScenarioSourceRequiresFlagInstaller(t *testing.T) {
	root := t.TempDir()
	for _, name := range requiredScenarioFiles {
		if name == "contents/scripts/install-flags.sh" {
			continue
		}
		path := filepath.Join(root, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, nil, 0o640); err != nil {
			t.Fatal(err)
		}
	}

	err := ValidateScenarioSource(root)
	if err == nil || !strings.Contains(err.Error(), "contents/scripts/install-flags.sh") {
		t.Fatalf("ValidateScenarioSource() error = %v, want missing install-flags.sh", err)
	}
}

func TestValidateScenarioSourceAllowsEmptyRequiredFiles(t *testing.T) {
	root := t.TempDir()
	for _, name := range requiredScenarioFiles {
		path := filepath.Join(root, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, nil, 0o640); err != nil {
			t.Fatal(err)
		}
	}

	if err := ValidateScenarioSource(root); err != nil {
		t.Fatal(err)
	}
}

func makeZIP(t *testing.T, files map[string]string) []byte {
	t.Helper()
	var buffer bytes.Buffer
	writer := zip.NewWriter(&buffer)
	for name, content := range files {
		entry, err := writer.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := entry.Write([]byte(content)); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}
