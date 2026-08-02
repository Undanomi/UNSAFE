package archive

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
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
