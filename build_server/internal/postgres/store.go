package postgres

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"strings"

	"github.com/Undanomi/SLSG/build_server/internal/domain"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/*.sql
var migrations embed.FS

var ErrNotFound = errors.New("not found")
var ErrConflict = errors.New("conflict")

// migrationLockID serializes schema setup across independently started API and
// worker processes. PostgreSQL's CREATE TABLE IF NOT EXISTS does not prevent
// concurrent catalog creation races by itself.
const migrationLockID int64 = 6000282982617766212

type Store struct{ pool *pgxpool.Pool }

func Open(ctx context.Context, databaseURL string) (*Store, error) {
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("open database: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping database: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close() { s.pool.Close() }

func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

func (s *Store) Migrate(ctx context.Context) error {
	body, err := migrations.ReadFile("migrations/001_init.sql")
	if err != nil {
		return fmt.Errorf("read migration: %w", err)
	}
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin migration: %w", err)
	}
	defer tx.Rollback(ctx)
	if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock($1)`, migrationLockID); err != nil {
		return fmt.Errorf("acquire migration lock: %w", err)
	}
	if _, err := tx.Exec(ctx, string(body)); err != nil {
		return fmt.Errorf("apply migration: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("commit migration: %w", err)
	}
	return nil
}

const buildColumns = `build_id::text, scenario_id, scenario_version_id, requested_by,
status, progress, worker_id, queued_at, started_at, completed_at, error_message, cancel_requested`

func scanBuild(row pgx.Row) (domain.Build, error) {
	var b domain.Build
	err := row.Scan(&b.ID, &b.ScenarioID, &b.ScenarioVersionID, &b.RequestedBy,
		&b.Status, &b.Progress, &b.WorkerID, &b.QueuedAt, &b.StartedAt,
		&b.CompletedAt, &b.ErrorMessage, &b.CancelRequested)
	if errors.Is(err, pgx.ErrNoRows) {
		return b, ErrNotFound
	}
	return b, err
}

func (s *Store) CreateBuild(ctx context.Context, id, scenarioID, versionID, requestedBy, key string) (domain.Build, bool, error) {
	b, err := scanBuild(s.pool.QueryRow(ctx, `INSERT INTO build_jobs
		(build_id, scenario_id, scenario_version_id, requested_by, idempotency_key, status)
		VALUES ($1::uuid, $2, $3, $4, $5, 'queued')
		ON CONFLICT (requested_by, idempotency_key) DO NOTHING
		RETURNING `+buildColumns, id, scenarioID, versionID, requestedBy, key))
	if err == nil {
		_ = s.AddEvent(ctx, id, "queued", "build queued", 0)
		return b, true, nil
	}
	if !errors.Is(err, ErrNotFound) {
		return b, false, err
	}
	b, err = scanBuild(s.pool.QueryRow(ctx, `SELECT `+buildColumns+`
		FROM build_jobs WHERE requested_by=$1 AND idempotency_key=$2`, requestedBy, key))
	if err == nil && (b.ScenarioID != scenarioID || b.ScenarioVersionID != versionID) {
		return b, false, ErrConflict
	}
	return b, false, err
}

func (s *Store) GetBuild(ctx context.Context, id string) (domain.Build, error) {
	return scanBuild(s.pool.QueryRow(ctx, `SELECT `+buildColumns+` FROM build_jobs WHERE build_id=$1::uuid`, id))
}

func (s *Store) AddEvent(ctx context.Context, id, eventType, message string, progress int) error {
	_, err := s.pool.Exec(ctx, `INSERT INTO build_events(build_id,event_type,message,progress)
		VALUES($1::uuid,$2,$3,$4)`, id, eventType, message, progress)
	return err
}

func (s *Store) Events(ctx context.Context, id string, after int64) ([]domain.Event, error) {
	rows, err := s.pool.Query(ctx, `SELECT build_event_id,build_id::text,event_type,message,progress,created_at
		FROM build_events WHERE build_id=$1::uuid AND build_event_id>$2 ORDER BY build_event_id LIMIT 500`, id, after)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	events, err := pgx.CollectRows(rows, pgx.RowToStructByPos[domain.Event])
	return events, err
}

func (s *Store) RequestCancel(ctx context.Context, id string) error {
	tag, err := s.pool.Exec(ctx, `UPDATE build_jobs SET
		cancel_requested=true,
		status=CASE WHEN status IN ('queued','retrying') THEN 'cancelled' ELSE status END,
		completed_at=CASE WHEN status IN ('queued','retrying') THEN now() ELSE completed_at END
		WHERE build_id=$1::uuid AND status NOT IN ('completed','failed','cancelled')`, id)
	if err == nil && tag.RowsAffected() == 0 {
		return ErrConflict
	}
	if err == nil {
		_ = s.AddEvent(ctx, id, "cancel_requested", "cancellation requested", 0)
	}
	return err
}

func (s *Store) Retry(ctx context.Context, id string) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	tag, err := tx.Exec(ctx, `UPDATE build_jobs SET status='retrying',progress=0,worker_id=NULL,
		started_at=NULL,completed_at=NULL,error_message=NULL,cancel_requested=false,queued_at=now()
		WHERE build_id=$1::uuid AND status IN ('failed','cancelled')`, id)
	if err == nil && tag.RowsAffected() == 0 {
		return ErrConflict
	}
	if err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `DELETE FROM build_artifacts WHERE build_id=$1::uuid`, id); err != nil {
		return err
	}
	if _, err := tx.Exec(ctx, `INSERT INTO build_events(build_id,event_type,message,progress)
		VALUES($1::uuid,'retrying','build queued for retry',0)`, id); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (s *Store) Claim(ctx context.Context, workerID string) (domain.Build, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return domain.Build{}, err
	}
	defer tx.Rollback(ctx)
	b, err := scanBuild(tx.QueryRow(ctx, `SELECT `+buildColumns+` FROM build_jobs
		WHERE status IN ('queued','retrying') AND cancel_requested=false
		ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT 1`))
	if err != nil {
		return domain.Build{}, err
	}
	_, err = tx.Exec(ctx, `UPDATE build_jobs SET status='validating',progress=5,worker_id=$2,started_at=now()
		WHERE build_id=$1::uuid`, b.ID, workerID)
	if err != nil {
		return domain.Build{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return domain.Build{}, err
	}
	b.Status, b.Progress, b.WorkerID = domain.StatusValidating, 5, &workerID
	_ = s.AddEvent(ctx, b.ID, "validating", "worker claimed build", 5)
	return b, nil
}

func (s *Store) SetStatus(ctx context.Context, id string, status domain.Status, progress int, message string) error {
	completed := status == domain.StatusCompleted || status == domain.StatusFailed || status == domain.StatusCancelled
	_, err := s.pool.Exec(ctx, `UPDATE build_jobs SET status=$2,progress=$3,
		completed_at=CASE WHEN $4 THEN now() ELSE completed_at END,
		error_message=CASE WHEN $2='failed' THEN $5 ELSE error_message END
		WHERE build_id=$1::uuid`, id, status, progress, completed, nullIfEmpty(message))
	if err == nil {
		err = s.AddEvent(ctx, id, string(status), message, progress)
	}
	return err
}

func (s *Store) CancelRequested(ctx context.Context, id string) (bool, error) {
	var requested bool
	err := s.pool.QueryRow(ctx, `SELECT cancel_requested FROM build_jobs WHERE build_id=$1::uuid`, id).Scan(&requested)
	return requested, err
}

func (s *Store) AddArtifact(ctx context.Context, artifact domain.Artifact) error {
	_, err := s.pool.Exec(ctx, `INSERT INTO build_artifacts
		(artifact_id,build_id,artifact_type,file_name,file_size,checksum)
		VALUES($1::uuid,$2::uuid,$3,$4,$5,$6)`,
		artifact.ID, artifact.BuildID, artifact.Type, artifact.FileName, artifact.FileSize, artifact.Checksum)
	return err
}

func (s *Store) Artifacts(ctx context.Context, buildID string) ([]domain.Artifact, error) {
	rows, err := s.pool.Query(ctx, `SELECT artifact_id::text,build_id::text,artifact_type,file_name,file_size,checksum,created_at
		FROM build_artifacts WHERE build_id=$1::uuid ORDER BY created_at`, buildID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return pgx.CollectRows(rows, pgx.RowToStructByPos[domain.Artifact])
}

func (s *Store) Artifact(ctx context.Context, buildID, artifactID string) (domain.Artifact, error) {
	var a domain.Artifact
	err := s.pool.QueryRow(ctx, `SELECT artifact_id::text,build_id::text,artifact_type,file_name,file_size,checksum,created_at
		FROM build_artifacts WHERE build_id=$1::uuid AND artifact_id=$2::uuid`, buildID, artifactID).
		Scan(&a.ID, &a.BuildID, &a.Type, &a.FileName, &a.FileSize, &a.Checksum, &a.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return a, ErrNotFound
	}
	return a, err
}

func nullIfEmpty(v string) any {
	if strings.TrimSpace(v) == "" {
		return nil
	}
	return v
}
