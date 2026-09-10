package config

import (
	"strings"
	"testing"
)

func TestServerFromEnvRequiresInternalAPIToken(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://build-service")
	t.Setenv("INTERNAL_API_TOKEN", "")

	_, err := ServerFromEnv()
	if err == nil || !strings.Contains(err.Error(), "INTERNAL_API_TOKEN is required") {
		t.Fatalf("ServerFromEnv() error = %v, want missing token error", err)
	}
}

func TestServerFromEnvReadsInternalAPIToken(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://build-service")
	t.Setenv("INTERNAL_API_TOKEN", "test-internal-api-token-32-characters")

	cfg, err := ServerFromEnv()
	if err != nil {
		t.Fatalf("ServerFromEnv() error = %v", err)
	}
	if cfg.InternalToken != "test-internal-api-token-32-characters" {
		t.Fatalf("InternalToken = %q, want configured token", cfg.InternalToken)
	}
}

func TestServerFromEnvRejectsShortInternalAPIToken(t *testing.T) {
	t.Setenv("DATABASE_URL", "postgres://build-service")
	t.Setenv("INTERNAL_API_TOKEN", "local-development-token")

	_, err := ServerFromEnv()
	if err == nil || !strings.Contains(err.Error(), "at least 32 characters") {
		t.Fatalf("ServerFromEnv() error = %v, want short token error", err)
	}
}
