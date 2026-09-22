package worker

import (
	"archive/zip"
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"time"
	"unicode"

	"github.com/Undanomi/SLSG/build_server/internal/buildlog"
	"github.com/Undanomi/SLSG/build_server/internal/config"
	"github.com/Undanomi/SLSG/build_server/internal/domain"
	"github.com/Undanomi/SLSG/build_server/internal/identity"
	"github.com/Undanomi/SLSG/build_server/internal/postgres"
)

const (
	storedErrorRunes        = 16_000
	machinePasswordBytes    = 24
	driveConversionMarker   = "Converting hard drive..."
	driveConversionProgress = 80
	driveConversionMessage  = "converting hard drive image"
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
	if err := w.migrateLegacyArtifacts(ctx); err != nil {
		return fmt.Errorf("migrate legacy artifacts: %w", err)
	}
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

func (w *Worker) migrateLegacyArtifacts(ctx context.Context) error {
	artifacts, err := w.store.LegacyDistributionArtifacts(ctx)
	if err != nil {
		return err
	}
	for _, artifact := range artifacts {
		if err := w.migrateLegacyArtifact(ctx, artifact); err != nil {
			if errors.Is(err, context.Canceled) {
				return err
			}
			w.logger.Error(
				"legacy artifact migration failed",
				"artifact_id", artifact.ID,
				"build_id", artifact.BuildID,
				"error", err,
			)
			continue
		}
		w.logger.Info(
			"legacy artifact migrated to zip",
			"artifact_id", artifact.ID,
			"build_id", artifact.BuildID,
		)
	}
	return nil
}

func (w *Worker) migrateLegacyArtifact(ctx context.Context, artifact domain.Artifact) error {
	artifactDir := filepath.Join(w.cfg.BuildRoot, artifact.BuildID, "artifacts")
	legacyPath := filepath.Join(artifactDir, filepath.Base(artifact.FileName))
	zipName := distributionFileName(artifact.ID)
	zipPath := filepath.Join(artifactDir, zipName)
	if _, err := os.Stat(zipPath); errors.Is(err, os.ErrNotExist) {
		if err := convertLegacyTarZst(ctx, legacyPath, zipPath); err != nil {
			return err
		}
	} else if err != nil {
		return err
	}
	if err := validateDistributionZip(zipPath); err != nil {
		return err
	}
	info, err := os.Stat(zipPath)
	if err != nil {
		return err
	}
	checksum, err := fileChecksum(zipPath)
	if err != nil {
		return err
	}
	artifact.Type = "zip"
	artifact.FileName = zipName
	artifact.FileSize = info.Size()
	artifact.Checksum = checksum
	if err := w.store.UpdateArtifactFile(ctx, artifact); err != nil {
		return err
	}
	if legacyPath != zipPath {
		if err := os.Remove(legacyPath); err != nil && !errors.Is(err, os.ErrNotExist) {
			w.logger.Warn(
				"legacy artifact metadata migrated but old file could not be removed",
				"artifact_id", artifact.ID,
				"path", legacyPath,
				"error", err,
			)
		}
	}
	return nil
}

func convertLegacyTarZst(ctx context.Context, legacyPath, zipPath string) error {
	expected, err := legacyTarEntries(ctx, legacyPath)
	if err != nil {
		return err
	}
	stagingDir, err := os.MkdirTemp(filepath.Dir(zipPath), ".legacy-artifact-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stagingDir)
	command := exec.CommandContext(
		ctx,
		"tar",
		"--zstd",
		"--extract",
		"--file", legacyPath,
		"--directory", stagingDir,
		"--no-same-owner",
		"--no-same-permissions",
	)
	if output, err := command.CombinedOutput(); err != nil {
		return fmt.Errorf("extract legacy artifact: %w: %s", err, strings.TrimSpace(string(output)))
	}
	sourceDir := filepath.Join(stagingDir, "slsg-machine")
	names, err := artifactFileNames(sourceDir)
	if err != nil {
		return err
	}
	if len(names) != len(expected) {
		return fmt.Errorf("legacy artifact entries changed during extraction")
	}
	for index := range names {
		if names[index] != expected[index] {
			return fmt.Errorf("legacy artifact entry mismatch: got %q, want %q", names[index], expected[index])
		}
	}
	temporary, err := os.CreateTemp(filepath.Dir(zipPath), ".artifact-*.zip")
	if err != nil {
		return err
	}
	temporaryPath := temporary.Name()
	if err := temporary.Close(); err != nil {
		return err
	}
	if err := os.Remove(temporaryPath); err != nil {
		return err
	}
	defer os.Remove(temporaryPath)
	if err := createDistributionZip(ctx, sourceDir, temporaryPath, names); err != nil {
		return err
	}
	return os.Rename(temporaryPath, zipPath)
}

func legacyTarEntries(ctx context.Context, archivePath string) ([]string, error) {
	command := exec.CommandContext(ctx, "tar", "--zstd", "--list", "--file", archivePath)
	output, err := command.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("list legacy artifact: %w: %s", err, strings.TrimSpace(string(output)))
	}
	seen := make(map[string]struct{})
	names := make([]string, 0)
	for _, rawName := range strings.Split(string(output), "\n") {
		rawName = strings.TrimSpace(rawName)
		if rawName == "" {
			continue
		}
		cleanName := strings.TrimSuffix(path.Clean(rawName), "/")
		if cleanName == "slsg-machine" {
			continue
		}
		if !strings.HasPrefix(cleanName, "slsg-machine/") {
			return nil, fmt.Errorf("legacy artifact contains unsafe entry %q", rawName)
		}
		name := strings.TrimPrefix(cleanName, "slsg-machine/")
		if name == "" || name == "." || name == ".." || strings.Contains(name, "/") {
			return nil, fmt.Errorf("legacy artifact contains unsupported entry %q", rawName)
		}
		if _, duplicate := seen[name]; duplicate {
			return nil, fmt.Errorf("legacy artifact contains duplicate entry %q", rawName)
		}
		seen[name] = struct{}{}
		names = append(names, name)
	}
	if _, ok := seen["image.qcow2"]; !ok {
		return nil, errors.New("legacy artifact does not contain image.qcow2")
	}
	sort.Strings(names)
	return names, nil
}

func validateDistributionZip(archivePath string) error {
	archive, err := zip.OpenReader(archivePath)
	if err != nil {
		return err
	}
	defer archive.Close()
	foundImage := false
	seen := make(map[string]struct{})
	for _, file := range archive.File {
		if file.FileInfo().IsDir() || file.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("zip contains unsupported entry %q", file.Name)
		}
		cleanName := path.Clean(file.Name)
		if !strings.HasPrefix(cleanName, "slsg-machine/") {
			return fmt.Errorf("zip contains unsafe entry %q", file.Name)
		}
		name := strings.TrimPrefix(cleanName, "slsg-machine/")
		if name == "" || name == "." || name == ".." || strings.Contains(name, "/") {
			return fmt.Errorf("zip contains unsupported entry %q", file.Name)
		}
		if _, duplicate := seen[name]; duplicate {
			return fmt.Errorf("zip contains duplicate entry %q", file.Name)
		}
		seen[name] = struct{}{}
		if name == "image.qcow2" {
			foundImage = true
		}
	}
	if !foundImage {
		return errors.New("zip does not contain image.qcow2")
	}
	return nil
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
	machinePassword, err := newMachinePassword()
	if err != nil {
		return fmt.Errorf("generate machine password: %w", err)
	}
	if err := w.runPacker(
		ctx, build.ID, workspaceDir, temporaryDir, baseImage, machinePassword, logFile, logger,
	); err != nil {
		return err
	}
	if err := w.store.SetMachinePassword(ctx, build.ID, machinePassword); err != nil {
		return fmt.Errorf("store machine password: %w", err)
	}
	if err := logFile.Sync(); err != nil {
		return err
	}
	if err := copyLauncherAssets(w.cfg.LauncherRoot, temporaryDir); err != nil {
		return fmt.Errorf("add launcher assets: %w", err)
	}
	artifactID, err := identity.NewUUID()
	if err != nil {
		return fmt.Errorf("generate artifact ID: %w", err)
	}
	if err := packageArtifacts(ctx, temporaryDir, workspaceDir, distributionFileName(artifactID)); err != nil {
		return fmt.Errorf("package build artifacts: %w", err)
	}

	if err := w.store.SetStatus(ctx, build.ID, domain.StatusUploading, 90, "registering build artifacts"); err != nil {
		return err
	}
	if err := os.Rename(temporaryDir, artifactDir); err != nil {
		return fmt.Errorf("publish artifacts atomically: %w", err)
	}
	if err := w.registerArtifact(ctx, build.ID, artifactID, artifactDir); err != nil {
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
	buildID string,
	workspaceDir string,
	outputDir string,
	baseImage string,
	machinePassword string,
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
	command.Env = append(
		os.Environ(),
		"CHECKPOINT_DISABLE=1",
		"PKR_VAR_machine_password="+machinePassword,
	)
	if err := command.Start(); err != nil {
		return fmt.Errorf("start packer: %w", err)
	}
	scanner := bufio.NewScanner(io.TeeReader(stdout, logFile))
	scanner.Buffer(make([]byte, 64*1024), 1024*1024)
	driveConversionReported := false
	for scanner.Scan() {
		line := scanner.Text()
		logger.Info("packer", "message", line)
		progress, message, driveConversionStarted := driveConversionUpdate(line)
		if !driveConversionReported && driveConversionStarted {
			driveConversionReported = true
			if err := w.store.SetStatus(
				ctx,
				buildID,
				domain.StatusBuilding,
				progress,
				message,
			); err != nil {
				logger.Warn("could not report drive conversion progress", "error", err)
			}
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read packer output: %w", err)
	}
	if err := command.Wait(); err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if syncErr := logFile.Sync(); syncErr != nil {
			logger.Warn("could not sync packer log", "error", syncErr)
		}
		logTail, tailErr := buildlog.Tail(
			logFile.Name(), buildlog.TailBytes, buildlog.TailLines,
		)
		if tailErr != nil {
			logger.Warn("could not read packer log tail", "error", tailErr)
		}
		if logTail != "" {
			return fmt.Errorf("packer build: %w\nrecent packer output:\n%s", err, logTail)
		}
		return fmt.Errorf("packer build: %w", err)
	}
	return nil
}

func driveConversionUpdate(line string) (int, string, bool) {
	if !strings.Contains(line, driveConversionMarker) {
		return 0, "", false
	}
	return driveConversionProgress, driveConversionMessage, true
}

func newMachinePassword() (string, error) {
	value := make([]byte, machinePasswordBytes)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(value), nil
}

func (w *Worker) registerArtifact(ctx context.Context, buildID, artifactID, artifactDir string) error {
	name := distributionFileName(artifactID)
	path := filepath.Join(artifactDir, name)
	info, err := os.Stat(path)
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return fmt.Errorf("distribution artifact %q is not a regular file", name)
	}
	checksum, err := fileChecksum(path)
	if err != nil {
		return err
	}
	return w.store.AddArtifact(ctx, domain.Artifact{
		ID: artifactID, BuildID: buildID, Type: "zip",
		FileName: name, FileSize: info.Size(), Checksum: checksum,
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

func copyLauncherAssets(source, destination string) error {
	entries, err := os.ReadDir(source)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if entry.IsDir() || entry.Type()&os.ModeSymlink != 0 || !entry.Type().IsRegular() {
			return fmt.Errorf("launcher directory contains unsupported entry %q", entry.Name())
		}
		inputPath := filepath.Join(source, entry.Name())
		outputPath := filepath.Join(destination, entry.Name())
		input, err := os.Open(inputPath)
		if err != nil {
			return err
		}
		mode := os.FileMode(0o640)
		if strings.EqualFold(filepath.Ext(entry.Name()), ".sh") {
			mode = 0o750
		}
		output, err := os.OpenFile(outputPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, mode)
		if err != nil {
			input.Close()
			return err
		}
		_, copyErr := io.Copy(output, input)
		inputErr := input.Close()
		outputErr := output.Close()
		if copyErr != nil {
			return copyErr
		}
		if inputErr != nil {
			return inputErr
		}
		if outputErr != nil {
			return outputErr
		}
	}
	return nil
}

func packageArtifacts(ctx context.Context, sourceDir, workDir, archiveName string) error {
	names, err := artifactFileNames(sourceDir)
	if err != nil {
		return err
	}

	temporaryArchive := filepath.Join(workDir, archiveName+".partial")
	if err := os.Remove(temporaryArchive); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	defer os.Remove(temporaryArchive)
	if err := createDistributionZip(ctx, sourceDir, temporaryArchive, names); err != nil {
		return fmt.Errorf("create %s: %w", archiveName, err)
	}

	for _, name := range names {
		if err := os.Remove(filepath.Join(sourceDir, name)); err != nil {
			return fmt.Errorf("remove packaged artifact %q: %w", name, err)
		}
	}
	return os.Rename(temporaryArchive, filepath.Join(sourceDir, archiveName))
}

func artifactFileNames(sourceDir string) ([]string, error) {
	entries, err := os.ReadDir(sourceDir)
	if err != nil {
		return nil, err
	}
	if len(entries) == 0 {
		return nil, errors.New("artifact directory is empty")
	}
	names := make([]string, 0, len(entries))
	hasImage := false
	for _, entry := range entries {
		if entry.IsDir() || entry.Type()&os.ModeSymlink != 0 || !entry.Type().IsRegular() {
			return nil, fmt.Errorf("artifact directory contains unsupported entry %q", entry.Name())
		}
		if entry.Name() == "image.qcow2" {
			hasImage = true
		}
		names = append(names, entry.Name())
	}
	if !hasImage {
		return nil, errors.New("artifact directory does not contain image.qcow2")
	}
	sort.Strings(names)
	return names, nil
}

func distributionFileName(artifactID string) string {
	return artifactID + ".zip"
}

func createDistributionZip(ctx context.Context, sourceDir, destination string, names []string) error {
	output, err := os.OpenFile(destination, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o640)
	if err != nil {
		return err
	}
	archive := zip.NewWriter(output)
	closeWithError := func(original error) error {
		_ = archive.Close()
		_ = output.Close()
		return original
	}
	for _, name := range names {
		select {
		case <-ctx.Done():
			return closeWithError(ctx.Err())
		default:
		}
		input, err := os.Open(filepath.Join(sourceDir, name))
		if err != nil {
			return closeWithError(err)
		}
		info, err := input.Stat()
		if err != nil {
			_ = input.Close()
			return closeWithError(err)
		}
		header, err := zip.FileInfoHeader(info)
		if err != nil {
			_ = input.Close()
			return closeWithError(err)
		}
		header.Name = "slsg-machine/" + name
		header.Method = zip.Deflate
		entry, err := archive.CreateHeader(header)
		if err != nil {
			_ = input.Close()
			return closeWithError(err)
		}
		_, copyErr := copyWithContext(ctx, entry, input)
		closeErr := input.Close()
		if copyErr != nil {
			return closeWithError(copyErr)
		}
		if closeErr != nil {
			return closeWithError(closeErr)
		}
	}
	if err := archive.Close(); err != nil {
		_ = output.Close()
		return err
	}
	return output.Close()
}

func copyWithContext(ctx context.Context, destination io.Writer, source io.Reader) (int64, error) {
	buffer := make([]byte, 1024*1024)
	var written int64
	for {
		select {
		case <-ctx.Done():
			return written, ctx.Err()
		default:
		}
		read, readErr := source.Read(buffer)
		if read > 0 {
			count, writeErr := destination.Write(buffer[:read])
			written += int64(count)
			if writeErr != nil {
				return written, writeErr
			}
			if count != read {
				return written, io.ErrShortWrite
			}
		}
		if errors.Is(readErr, io.EOF) {
			return written, nil
		}
		if readErr != nil {
			return written, readErr
		}
	}
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
	case ".zip":
		return "zip"
	case ".qcow2":
		return "qcow2"
	case ".vmdk":
		return "vmdk"
	case ".iso":
		return "iso"
	case ".sh", ".ps1":
		return "launcher"
	case ".md":
		return "documentation"
	default:
		return "file"
	}
}

func sanitizeError(err error) string {
	message := strings.Map(func(character rune) rune {
		if character == '\n' || character == '\t' || !unicode.IsControl(character) {
			return character
		}
		return ' '
	}, err.Error())
	runes := []rune(strings.TrimSpace(message))
	if len(runes) > storedErrorRunes {
		const prefixRunes = 2_000
		return string(runes[:prefixRunes]) +
			"\n...[older output truncated]...\n" +
			string(runes[len(runes)-(storedErrorRunes-prefixRunes):])
	}
	return string(runes)
}
