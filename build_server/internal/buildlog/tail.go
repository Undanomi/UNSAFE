package buildlog

import (
	"io"
	"os"
	"strings"
)

const (
	TailBytes = 64 << 10
	TailLines = 120
)

// Tail returns a bounded, line-aligned excerpt from the end of a build log.
func Tail(path string, maxBytes int64, maxLines int) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return "", err
	}
	start := max(info.Size()-maxBytes, 0)
	if _, err := file.Seek(start, io.SeekStart); err != nil {
		return "", err
	}
	content, err := io.ReadAll(io.LimitReader(file, maxBytes))
	if err != nil {
		return "", err
	}
	text := strings.ReplaceAll(string(content), "\r\n", "\n")
	if start > 0 {
		if firstLineEnd := strings.IndexByte(text, '\n'); firstLineEnd >= 0 {
			text = text[firstLineEnd+1:]
		}
	}
	text = strings.TrimRight(text, "\n")
	if text == "" {
		return "", nil
	}
	lines := strings.Split(text, "\n")
	if maxLines > 0 && len(lines) > maxLines {
		lines = lines[len(lines)-maxLines:]
	}
	return strings.TrimSpace(strings.Join(lines, "\n")), nil
}
