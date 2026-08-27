package worker

import (
	"bufio"
	"context"
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/Undanomi/SLSG/build_server/internal/config"
	"github.com/Undanomi/SLSG/build_server/internal/domain"
	"github.com/Undanomi/SLSG/build_server/internal/identity"
	"github.com/Undanomi/SLSG/build_server/internal/postgres"
)

type Worker struct {
	cfg    config.Worker
	store  *postgres.Store
	logger *slog.Logger
}

func New(cfg config.Worker, store *postgres.Store, logger *slog.Logger) *Worker {
	return &Worker{cfg: cfg, store: store, logger: logger}
}

func (w *Worker) Run(ctx context.Context) error {
	ticker := time.NewTicker(w.cfg.PollInterval)
	defer ticker.Stop()
	for {
		if err := w.runNext(ctx); err != nil && !errors.Is(err, postgres.ErrNotFound) {
			w.logger.Error("worker iteration failed", "worker_id", w.cfg.WorkerID, "error", err)
		}
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

func (w *Worker) runNext(ctx context.Context) error {
	build, err := w.store.Claim(ctx, w.cfg.WorkerID)
	if err != nil {
		return err
	}
	logger := w.logger.With("build_id", build.ID, "scenario_id", build.ScenarioID)
	logger.Info("build claimed")
	if err := w.execute(ctx, build, logger); err != nil {
		if errors.Is(err, context.Canceled) || w.isCancellationRequested(context.Background(), build.ID) {
			_ = w.store.SetStatus(context.Background(), build.ID, domain.StatusCancelled, build.Progress, "build cancelled")
			logger.Info("build cancelled")
			return nil
		}
		_ = w.store.SetStatus(context.Background(), build.ID, domain.StatusFailed, build.Progress, sanitizeError(err))
		logger.Error("build failed", "error", err)
		return nil
	}
	return nil
}

func (w *Worker) execute(parent context.Context, build domain.Build, logger *slog.Logger) error {
	ctx, cancel := context.WithTimeout(parent, w.cfg.BuildTimeout)
	defer cancel()
	ctx, cancelOnRequest := context.WithCancel(ctx)
	defer cancelOnRequest()
	go w.watchCancellation(ctx, build.ID, cancelOnRequest)

	sourceDir := filepath.Join(w.cfg.ScenarioRoot, "uploads", build.ID, "source")
	if err := validateSourceDir(sourceDir); err != nil {
		return err
	}
	if err := w.store.SetStatus(ctx, build.ID, domain.StatusPreparing, 10, "preparing isolated workspace"); err != nil {
		return err
	}

	buildDir := filepath.Join(w.cfg.BuildRoot, build.ID)
	workspaceDir := filepath.Join(buildDir, "workspace")
	logDir := filepath.Join(buildDir, "logs")
	temporaryDir := filepath.Join(buildDir, "temporary")
	artifactDir := filepath.Join(buildDir, "artifacts")
	for _, dir := range []string{workspaceDir, temporaryDir, artifactDir} {
		if err := os.RemoveAll(dir); err != nil {
			return fmt.Errorf("clear previous build attempt: %w", err)
		}
	}
	// Packer's QEMU builder requires output_dir itself not to exist. Create
	// only its parent directories and let Packer create temporaryDir.
	for _, dir := range []string{workspaceDir, logDir} {
		if err := os.MkdirAll(dir, 0o750); err != nil {
			return fmt.Errorf("create build directory: %w", err)
		}
	}
	if err := copyTree(sourceDir, filepath.Join(workspaceDir, "source")); err != nil {
		return fmt.Errorf("copy scenario source: %w", err)
	}
	baseImage, err := resolveBaseImage(sourceDir, w.cfg.BaseImageRoot)
	if err != nil {
		return err
	}

	logPath := filepath.Join(logDir, "packer.log")
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o640)
	if err != nil {
		return fmt.Errorf("open packer log: %w", err)
	}
	defer logFile.Close()

	if err := w.store.SetStatus(ctx, build.ID, domain.StatusBuilding, 20, "packer build started"); err != nil {
		return err
	}
	if err := w.runPacker(ctx, workspaceDir, temporaryDir, baseImage, logFile, logger); err != nil {
		return err
	}
	if err := logFile.Sync(); err != nil {
		return err
	}

	if err := w.store.SetStatus(ctx, build.ID, domain.StatusUploading, 90, "registering build artifacts"); err != nil {
		return err
	}
	if err := os.Rename(temporaryDir, artifactDir); err != nil {
		return fmt.Errorf("publish artifacts atomically: %w", err)
	}
	if err := w.registerArtifacts(ctx, build.ID, artifactDir); err != nil {
		return err
	}
	if err := w.store.SetStatus(ctx, build.ID, domain.StatusCompleted, 100, "build completed"); err != nil {
		return err
	}
	logger.Info("build completed")
	return nil
}

func (w *Worker) runPacker(
	ctx context.Context,
	workspaceDir string,
	outputDir string,
	baseImage string,
	logFile *os.File,
	logger *slog.Logger,
) error {
	command := exec.CommandContext(ctx, w.cfg.PackerBinary, "build",
		"-color=false",
		"-var", "base_image="+baseImage,
		"-var", "source_dir="+filepath.Join(workspaceDir, "source"),
		"-var", "output_dir="+outputDir,
		w.cfg.PackerTemplate,
	)
	stdout, err := command.StdoutPipe()
	if err != nil {
		return err
	}
	command.Stderr = logFile
	command.Env = append(os.Environ(), "CHECKPOINT_DISABLE=1")
	if err := command.Start(); err != nil {
		return fmt.Errorf("start packer: %w", err)
	}
	scanner := bufio.NewScanner(io.TeeReader(stdout, logFile))
	scanner.Buffer(make([]byte, 64*1024), 1024*1024)
	diagnostic := ""
	diagnosticScore := 0
	for scanner.Scan() {
		line := scanner.Text()
		logger.Info("packer", "message", line)
		if score := packerDiagnosticScore(line); score > diagnosticScore {
			diagnostic = strings.TrimSpace(line)
			diagnosticScore = score
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read packer output: %w", err)
	}
	if err := command.Wait(); err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if diagnostic != "" {
			return fmt.Errorf("packer build: %w: %s", err, diagnostic)
		}
		return fmt.Errorf("packer build: %w", err)
	}
	return nil
}

func packerDiagnosticScore(line string) int {
	lower := strings.ToLower(line)
	switch {
	case strings.Contains(lower, "unable to locate"):
		return 100
	case strings.Contains(lower, "job for ") && strings.Contains(lower, " failed"):
		return 90
	case strings.Contains(lower, "command not found") || strings.Contains(lower, "no such file"):
		return 85
	case strings.Contains(lower, "error:"):
		return 80
	default:
		return 0
	}
}

func (w *Worker) registerArtifacts(ctx context.Context, buildID, artifactDir string) error {
	return filepath.WalkDir(artifactDir, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		// Keep the public artifact layout flat and reject unexpected nested output.
		if filepath.Dir(path) != artifactDir {
			return fmt.Errorf("packer produced nested artifact %q", entry.Name())
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		checksum, err := fileChecksum(path)
		if err != nil {
			return err
		}
		id, err := identity.NewUUID()
		if err != nil {
			return err
		}
		return w.store.AddArtifact(ctx, domain.Artifact{
			ID: id, BuildID: buildID, Type: artifactType(entry.Name()),
			FileName: entry.Name(), FileSize: info.Size(), Checksum: checksum,
		})
	})
}

func (w *Worker) watchCancellation(ctx context.Context, buildID string, cancel context.CancelFunc) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if w.isCancellationRequested(ctx, buildID) {
				cancel()
				return
			}
		}
	}
}

func (w *Worker) isCancellationRequested(ctx context.Context, buildID string) bool {
	requested, err := w.store.CancelRequested(ctx, buildID)
	return err == nil && requested
}

func validateSourceDir(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		return fmt.Errorf("scenario source unavailable: %w", err)
	}
	if !info.IsDir() {
		return errors.New("scenario source is not a directory")
	}
	return nil
}

func copyTree(source, destination string) error {
	return filepath.WalkDir(source, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(source, path)
		if err != nil {
			return err
		}
		target := filepath.Join(destination, relative)
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("symbolic links are not allowed: %s", relative)
		}
		if entry.IsDir() {
			return os.MkdirAll(target, 0o750)
		}
		if !entry.Type().IsRegular() {
			return fmt.Errorf("unsupported source file type: %s", relative)
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if info.Size() > 100<<20 {
			return fmt.Errorf("source file exceeds 100 MiB limit: %s", relative)
		}
		input, err := os.Open(path)
		if err != nil {
			return err
		}
		output, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0o640)
		if err != nil {
			input.Close()
			return err
		}
		_, copyErr := io.Copy(output, input)
		inputErr := input.Close()
		closeErr := output.Close()
		if copyErr != nil {
			return copyErr
		}
		if inputErr != nil {
			return inputErr
		}
		return closeErr
	})
}

func fileChecksum(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return fmt.Sprintf("sha256:%x", hash.Sum(nil)), nil
}

func artifactType(name string) string {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".qcow2":
		return "qcow2"
	case ".vmdk":
		return "vmdk"
	case ".iso":
		return "iso"
	default:
		return "file"
	}
}

func sanitizeError(err error) string {
	message := strings.ReplaceAll(err.Error(), "\n", " ")
	if len(message) > 2000 {
		return message[:2000]
	}
	return message
}
