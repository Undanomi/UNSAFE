package worker

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const defaultTargetOS = "Debian 13.7.0"

var debianVersionPattern = regexp.MustCompile(`(?i)^debian\s+(\d+(?:\.\d+){0,2})$`)

type scenarioManifest struct {
	TargetOS string `json:"target_os"`
}

func resolveBaseImage(sourceDir, baseImageRoot string) (string, error) {
	manifestPath := filepath.Join(sourceDir, "contents", "scenario_manifest.json")
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		return "", fmt.Errorf("read scenario target OS: %w", err)
	}
	var manifest scenarioManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return "", fmt.Errorf("parse scenario target OS: %w", err)
	}
	targetOS := strings.TrimSpace(manifest.TargetOS)
	if targetOS == "" {
		targetOS = defaultTargetOS
	}
	match := debianVersionPattern.FindStringSubmatch(targetOS)
	if match == nil {
		return "", fmt.Errorf("unsupported target OS %q: only Debian base images are supported", targetOS)
	}
	imagePath := filepath.Join(baseImageRoot, "debian-"+match[1]+"-amd64.qcow2")
	info, err := os.Stat(imagePath)
	if err != nil {
		return "", fmt.Errorf("base image for %s is unavailable at %s: %w", targetOS, imagePath, err)
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("base image for %s is not a regular file", targetOS)
	}
	return imagePath, nil
}
