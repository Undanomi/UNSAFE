package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Common struct {
	DatabaseURL string
}

type Server struct {
	Common
	Address       string
	InternalToken string
	ArtifactRoot  string
	ScenarioRoot  string
}

type Worker struct {
	Common
	WorkerID       string
	ScenarioRoot   string
	BuildRoot      string
	BaseImageRoot  string
	LauncherRoot   string
	PackerBinary   string
	PackerTemplate string
	PollInterval   time.Duration
	BuildTimeout   time.Duration
}

func ServerFromEnv() (Server, error) {
	databaseURL, err := required("DATABASE_URL")
	if err != nil {
		return Server{}, err
	}
	internalToken, err := required("INTERNAL_API_TOKEN")
	if err != nil {
		return Server{}, err
	}
	if len(internalToken) < 32 {
		return Server{}, fmt.Errorf("INTERNAL_API_TOKEN must contain at least 32 characters")
	}
	return Server{
		Common:        Common{DatabaseURL: databaseURL},
		Address:       value("HTTP_ADDRESS", ":8080"),
		InternalToken: internalToken,
		ArtifactRoot:  value("BUILD_ROOT", "/var/lib/slsg/builds"),
		ScenarioRoot:  value("SCENARIO_ROOT", "/var/lib/slsg/scenarios"),
	}, nil
}

func WorkerFromEnv() (Worker, error) {
	databaseURL, err := required("DATABASE_URL")
	if err != nil {
		return Worker{}, err
	}
	workerID, err := required("WORKER_ID")
	if err != nil {
		return Worker{}, err
	}
	poll, err := duration("WORKER_POLL_INTERVAL", 2*time.Second)
	if err != nil {
		return Worker{}, err
	}
	timeout, err := duration("BUILD_TIMEOUT", 2*time.Hour)
	if err != nil {
		return Worker{}, err
	}
	return Worker{
		Common:         Common{DatabaseURL: databaseURL},
		WorkerID:       workerID,
		ScenarioRoot:   value("SCENARIO_ROOT", "/var/lib/slsg/scenarios"),
		BuildRoot:      value("BUILD_ROOT", "/var/lib/slsg/builds"),
		BaseImageRoot:  value("BASE_IMAGE_ROOT", "/opt/slsg/base_images"),
		LauncherRoot:   value("LAUNCHER_ROOT", "/opt/slsg/launchers"),
		PackerBinary:   value("PACKER_BINARY", "packer"),
		PackerTemplate: value("PACKER_TEMPLATE", "/opt/slsg/packer/build.pkr.hcl"),
		PollInterval:   poll,
		BuildTimeout:   timeout,
	}, nil
}

func required(key string) (string, error) {
	v := os.Getenv(key)
	if v == "" {
		return "", fmt.Errorf("%s is required", key)
	}
	return v, nil
}

func value(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func duration(key string, fallback time.Duration) (time.Duration, error) {
	v := os.Getenv(key)
	if v == "" {
		return fallback, nil
	}
	if seconds, err := strconv.Atoi(v); err == nil {
		return time.Duration(seconds) * time.Second, nil
	}
	parsed, err := time.ParseDuration(v)
	if err != nil {
		return 0, fmt.Errorf("%s must be a duration or seconds: %w", key, err)
	}
	return parsed, nil
}
