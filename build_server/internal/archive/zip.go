package archive

import (
	"archive/zip"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const (
	MaxCompressedSize   = 64 << 20
	MaxUncompressedSize = 512 << 20
	MaxFileSize         = 100 << 20
	MaxFiles            = 10_000
)

// ExtractZIP extracts a scenario archive into destination. The destination
// must not exist. Archive paths and file types are validated before any build
// can consume the result.
func ExtractZIP(source io.ReaderAt, compressedSize int64, destination string) error {
	if compressedSize <= 0 || compressedSize > MaxCompressedSize {
		return fmt.Errorf("ZIP size must be between 1 byte and %d bytes", MaxCompressedSize)
	}
	reader, err := zip.NewReader(source, compressedSize)
	if err != nil {
		return fmt.Errorf("invalid ZIP archive: %w", err)
	}
	if len(reader.File) == 0 {
		return errors.New("ZIP archive is empty")
	}
	if len(reader.File) > MaxFiles {
		return fmt.Errorf("ZIP archive contains more than %d entries", MaxFiles)
	}

	var total uint64
	for _, file := range reader.File {
		if err := validateEntry(file); err != nil {
			return err
		}
		total += file.UncompressedSize64
		if total > MaxUncompressedSize {
			return fmt.Errorf("expanded ZIP exceeds %d bytes", MaxUncompressedSize)
		}
	}

	if err := os.Mkdir(destination, 0o750); err != nil {
		return err
	}
	for _, file := range reader.File {
		if err := extractEntry(file, destination); err != nil {
			return err
		}
	}
	return nil
}

func validateEntry(file *zip.File) error {
	name := strings.ReplaceAll(file.Name, `\`, "/")
	clean := filepath.Clean(filepath.FromSlash(name))
	if name == "" || strings.ContainsRune(name, 0) || filepath.IsAbs(clean) ||
		clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return fmt.Errorf("unsafe ZIP path %q", file.Name)
	}
	mode := file.Mode()
	if mode&os.ModeSymlink != 0 || (!mode.IsRegular() && !mode.IsDir()) {
		return fmt.Errorf("unsupported ZIP entry type %q", file.Name)
	}
	if file.UncompressedSize64 > MaxFileSize {
		return fmt.Errorf("ZIP entry %q exceeds %d bytes", file.Name, MaxFileSize)
	}
	return nil
}

func extractEntry(file *zip.File, destination string) error {
	name := strings.ReplaceAll(file.Name, `\`, "/")
	target := filepath.Join(destination, filepath.Clean(filepath.FromSlash(name)))
	if file.FileInfo().IsDir() {
		return os.MkdirAll(target, 0o750)
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o750); err != nil {
		return err
	}
	input, err := file.Open()
	if err != nil {
		return err
	}
	output, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o640)
	if err != nil {
		input.Close()
		return err
	}
	_, copyErr := io.Copy(output, io.LimitReader(input, MaxFileSize+1))
	inputErr := input.Close()
	outputErr := output.Close()
	if copyErr != nil {
		return copyErr
	}
	if inputErr != nil {
		return inputErr
	}
	return outputErr
}
