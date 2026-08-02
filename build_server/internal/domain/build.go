package domain

import "time"

type Status string

const (
	StatusQueued     Status = "queued"
	StatusValidating Status = "validating"
	StatusPreparing  Status = "preparing"
	StatusBuilding   Status = "building"
	StatusUploading  Status = "uploading"
	StatusCompleted  Status = "completed"
	StatusFailed     Status = "failed"
	StatusCancelled  Status = "cancelled"
	StatusRetrying   Status = "retrying"
)

type Build struct {
	ID                string     `json:"build_id"`
	ScenarioID        string     `json:"scenario_id"`
	ScenarioVersionID string     `json:"scenario_version_id"`
	RequestedBy       string     `json:"requested_by"`
	Status            Status     `json:"status"`
	Progress          int        `json:"progress"`
	WorkerID          *string    `json:"worker_id,omitempty"`
	QueuedAt          time.Time  `json:"queued_at"`
	StartedAt         *time.Time `json:"started_at,omitempty"`
	CompletedAt       *time.Time `json:"completed_at,omitempty"`
	ErrorMessage      *string    `json:"error_message,omitempty"`
	CancelRequested   bool       `json:"cancel_requested"`
}

type Event struct {
	ID        int64     `json:"build_event_id"`
	BuildID   string    `json:"build_id"`
	Type      string    `json:"event_type"`
	Message   string    `json:"message"`
	Progress  int       `json:"progress"`
	CreatedAt time.Time `json:"created_at"`
}

type Artifact struct {
	ID        string    `json:"artifact_id"`
	BuildID   string    `json:"build_id"`
	Type      string    `json:"artifact_type"`
	FileName  string    `json:"file_name"`
	FileSize  int64     `json:"file_size"`
	Checksum  string    `json:"checksum"`
	CreatedAt time.Time `json:"created_at"`
}
