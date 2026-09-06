package domain

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestBuildJSONIncludesMachinePasswordWhenAssigned(t *testing.T) {
	password := "0123456789abcdefghijklmnopqrstuv"
	payload, err := json.Marshal(Build{MachinePassword: &password})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(payload), `"machine_password":"`+password+`"`) {
		t.Fatalf("Build JSON does not contain the assigned machine password: %s", payload)
	}
}

func TestBuildJSONOmitsMachinePasswordBeforeAssignment(t *testing.T) {
	payload, err := json.Marshal(Build{})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(payload), `"machine_password"`) {
		t.Fatalf("Build JSON contains an unassigned machine password: %s", payload)
	}
}
