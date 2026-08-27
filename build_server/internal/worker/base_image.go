package worker

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const defaultTargetOS = "Ubuntu 26.04"

var ubuntuVersionPattern = regexp.MustCompile(`(?i)^ubuntu\s+(\d{2}\.\d{2})(?:\s+lts)?$`)

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
	match := ubuntuVersionPattern.FindStringSubmatch(targetOS)
	if match == nil {
		return "", fmt.Errorf("unsupported target OS %q: only Ubuntu base images are supported", targetOS)
	}
	imagePath := filepath.Join(baseImageRoot, "ubuntu-"+match[1]+"-server.qcow2")
	info, err := os.Stat(imagePath)
	if err != nil {
		return "", fmt.Errorf("base image for %s is unavailable at %s: %w", targetOS, imagePath, err)
	}
	if !info.Mode().IsRegular() {
		return "", fmt.Errorf("base image for %s is not a regular file", targetOS)
	}
	return imagePath, nil
}
