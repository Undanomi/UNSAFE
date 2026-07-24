package identity

import (
	"regexp"
	"testing"
)

func TestNewUUID(t *testing.T) {
	id, err := NewUUID()
	if err != nil {
		t.Fatal(err)
	}
	pattern := regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`)
	if !pattern.MatchString(id) {
		t.Fatalf("NewUUID() = %q, want RFC 4122 version 4 UUID", id)
	}
}
