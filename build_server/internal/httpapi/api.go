package httpapi

import (
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/Undanomi/SLSG/build_server/internal/archive"
	"github.com/Undanomi/SLSG/build_server/internal/buildlog"
	"github.com/Undanomi/SLSG/build_server/internal/identity"
	"github.com/Undanomi/SLSG/build_server/internal/postgres"
)

var identifierPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)

type API struct {
	store         *postgres.Store
	logger        *slog.Logger
	internalToken string
	artifactRoot  string
	scenarioRoot  string
}

func New(store *postgres.Store, logger *slog.Logger, internalToken, artifactRoot, scenarioRoot string) http.Handler {
	api := &API{
		store: store, logger: logger, internalToken: internalToken,
		artifactRoot: artifactRoot, scenarioRoot: scenarioRoot,
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health/live", api.live)
	mux.HandleFunc("GET /health/ready", api.ready)
	mux.HandleFunc("POST /v1/builds", api.createBuild)
	mux.HandleFunc("GET /v1/builds/{buildID}", api.getBuild)
	mux.HandleFunc("POST /v1/builds/{buildID}/cancel", api.cancelBuild)
	mux.HandleFunc("POST /v1/builds/{buildID}/retry", api.retryBuild)
	mux.HandleFunc("GET /v1/builds/{buildID}/events", api.events)
	mux.HandleFunc("GET /v1/builds/{buildID}/logs/packer", api.packerLog)
	mux.HandleFunc("GET /v1/builds/{buildID}/artifacts", api.artifacts)
	mux.HandleFunc("GET /v1/builds/{buildID}/artifacts/{artifactID}/content", api.downloadArtifact)
	return requestLog(logger, recoverer(logger, api.authenticate(mux)))
}

func (a *API) authenticate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/health/") {
			next.ServeHTTP(w, r)
			return
		}
		if a.internalToken == "" {
			problem(w, http.StatusServiceUnavailable, "authentication unavailable", "Service authentication is not configured.")
			return
		}
		actual := []byte(r.Header.Get("Authorization"))
		expected := []byte("Bearer " + a.internalToken)
		if len(actual) != len(expected) || subtle.ConstantTimeCompare(actual, expected) != 1 {
			problem(w, http.StatusUnauthorized, "unauthorized", "A valid service token is required.")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (a *API) live(w http.ResponseWriter, _ *http.Request) {
	jsonResponse(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (a *API) ready(w http.ResponseWriter, r *http.Request) {
	if err := a.store.Ping(r.Context()); err != nil {
		problem(w, http.StatusServiceUnavailable, "database unavailable", "The database is not ready.")
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (a *API) createBuild(w http.ResponseWriter, r *http.Request) {
	r.Body = http.MaxBytesReader(w, r.Body, archive.MaxCompressedSize+(1<<20))
	if err := r.ParseMultipartForm(1 << 20); err != nil {
		problem(w, http.StatusBadRequest, "invalid multipart request", "Expected scenario fields and a ZIP file no larger than 64 MiB.")
		return
	}
	if r.MultipartForm != nil {
		defer r.MultipartForm.RemoveAll()
	}
	scenarioID := strings.TrimSpace(r.FormValue("scenario_id"))
	versionID := strings.TrimSpace(r.FormValue("scenario_version_id"))
	if !identifierPattern.MatchString(scenarioID) || !identifierPattern.MatchString(versionID) {
		problem(w, http.StatusBadRequest, "invalid identifier", "Scenario identifiers may only contain letters, numbers, dot, underscore, and hyphen.")
		return
	}
	source, header, err := r.FormFile("source")
	if err != nil {
		problem(w, http.StatusBadRequest, "missing source", "A ZIP file is required in the source form field.")
		return
	}
	defer source.Close()
	if header.Size <= 0 || header.Size > archive.MaxCompressedSize {
		problem(w, http.StatusBadRequest, "invalid source size", "The ZIP file must be no larger than 64 MiB.")
		return
	}
	requestedBy := strings.TrimSpace(r.Header.Get("X-Authenticated-User-ID"))
	if requestedBy == "" {
		problem(w, http.StatusBadRequest, "missing user", "X-Authenticated-User-ID is required.")
		return
	}
	key := strings.TrimSpace(r.Header.Get("Idempotency-Key"))
	if key == "" || len(key) > 200 {
		problem(w, http.StatusBadRequest, "invalid idempotency key", "Idempotency-Key is required and must be at most 200 characters.")
		return
	}
	id, err := identity.NewUUID()
	if err != nil {
		problem(w, http.StatusInternalServerError, "internal error", "Could not generate a build identifier.")
		return
	}

	uploadRoot := filepath.Join(a.scenarioRoot, "uploads")
	temporaryDir := filepath.Join(uploadRoot, id+".part")
	finalDir := filepath.Join(uploadRoot, id)
	if err := os.MkdirAll(temporaryDir, 0o750); err != nil {
		a.internalError(w, r, fmt.Errorf("create upload directory: %w", err))
		return
	}
	cleanup := true
	defer func() {
		if cleanup {
			_ = os.RemoveAll(temporaryDir)
			_ = os.RemoveAll(finalDir)
		}
	}()
	if err := archive.ExtractZIP(source, header.Size, filepath.Join(temporaryDir, "source")); err != nil {
		problem(w, http.StatusBadRequest, "invalid source archive", err.Error())
		return
	}
	if err := os.Rename(temporaryDir, finalDir); err != nil {
		a.internalError(w, r, fmt.Errorf("publish uploaded source: %w", err))
		return
	}

	build, created, err := a.store.CreateBuild(r.Context(), id, scenarioID, versionID, requestedBy, key)
	if err != nil {
		if errors.Is(err, postgres.ErrConflict) {
			problem(w, http.StatusConflict, "idempotency conflict", "The idempotency key was already used for different scenario identifiers.")
			return
		}
		a.internalError(w, r, err)
		return
	}
	if created {
		cleanup = false
	} else if err := os.RemoveAll(finalDir); err != nil {
		a.logger.Warn("could not remove duplicate upload", "path", finalDir, "error", err)
	}
	w.Header().Set("Location", "/v1/builds/"+build.ID)
	if created {
		jsonResponse(w, http.StatusAccepted, build)
		return
	}
	jsonResponse(w, http.StatusOK, build)
}

func (a *API) getBuild(w http.ResponseWriter, r *http.Request) {
	build, err := a.store.GetBuild(r.Context(), r.PathValue("buildID"))
	if err != nil {
		a.storeError(w, r, err)
		return
	}
	jsonResponse(w, http.StatusOK, build)
}

func (a *API) cancelBuild(w http.ResponseWriter, r *http.Request) {
	if err := a.store.RequestCancel(r.Context(), r.PathValue("buildID")); err != nil {
		a.storeError(w, r, err)
		return
	}
	w.WriteHeader(http.StatusAccepted)
}

func (a *API) retryBuild(w http.ResponseWriter, r *http.Request) {
	if err := a.store.Retry(r.Context(), r.PathValue("buildID")); err != nil {
		a.storeError(w, r, err)
		return
	}
	w.WriteHeader(http.StatusAccepted)
}

func (a *API) events(w http.ResponseWriter, r *http.Request) {
	after, err := strconv.ParseInt(valueOr(r.URL.Query().Get("after"), "0"), 10, 64)
	if err != nil || after < 0 {
		problem(w, http.StatusBadRequest, "invalid cursor", "after must be a non-negative integer.")
		return
	}
	events, err := a.store.Events(r.Context(), r.PathValue("buildID"), after)
	if err != nil {
		a.internalError(w, r, err)
		return
	}
	jsonResponse(w, http.StatusOK, map[string]any{"items": events})
}

func (a *API) packerLog(w http.ResponseWriter, r *http.Request) {
	build, err := a.store.GetBuild(r.Context(), r.PathValue("buildID"))
	if err != nil {
		a.storeError(w, r, err)
		return
	}
	path := filepath.Join(a.artifactRoot, build.ID, "logs", "packer.log")
	logTail, err := buildlog.Tail(path, buildlog.TailBytes, buildlog.TailLines)
	if errors.Is(err, os.ErrNotExist) {
		problem(w, http.StatusNotFound, "log missing", "The Packer log is not available.")
		return
	}
	if err != nil {
		a.internalError(w, r, fmt.Errorf("read packer log: %w", err))
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = io.WriteString(w, logTail)
}

func (a *API) artifacts(w http.ResponseWriter, r *http.Request) {
	artifacts, err := a.store.Artifacts(r.Context(), r.PathValue("buildID"))
	if err != nil {
		a.internalError(w, r, err)
		return
	}
	jsonResponse(w, http.StatusOK, map[string]any{"items": artifacts})
}

func (a *API) downloadArtifact(w http.ResponseWriter, r *http.Request) {
	artifact, err := a.store.Artifact(r.Context(), r.PathValue("buildID"), r.PathValue("artifactID"))
	if err != nil {
		a.storeError(w, r, err)
		return
	}
	// Both directory components come from UUID columns and the file name is generated by the worker.
	path := filepath.Join(a.artifactRoot, artifact.BuildID, "artifacts", filepath.Base(artifact.FileName))
	file, err := os.Open(path)
	if errors.Is(err, os.ErrNotExist) {
		problem(w, http.StatusNotFound, "artifact missing", "The artifact file is not available.")
		return
	}
	if err != nil {
		a.internalError(w, r, err)
		return
	}
	defer file.Close()
	w.Header().Set("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": artifact.FileName}))
	w.Header().Set("Content-Type", "application/zstd")
	http.ServeContent(w, r, artifact.FileName, artifact.CreatedAt, file)
}

func (a *API) storeError(w http.ResponseWriter, r *http.Request, err error) {
	switch {
	case errors.Is(err, postgres.ErrNotFound):
		problem(w, http.StatusNotFound, "not found", "The requested resource does not exist.")
	case errors.Is(err, postgres.ErrConflict):
		problem(w, http.StatusConflict, "invalid state", "The operation is not valid for the current build state.")
	default:
		a.internalError(w, r, err)
	}
}

func (a *API) internalError(w http.ResponseWriter, r *http.Request, err error) {
	a.logger.Error("request failed", "method", r.Method, "path", r.URL.Path, "error", err)
	problem(w, http.StatusInternalServerError, "internal error", "The request could not be completed.")
}

func jsonResponse(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func problem(w http.ResponseWriter, status int, title, detail string) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{
		"type": "about:blank", "title": title, "status": status, "detail": detail,
	})
}

func requestLog(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("request", "method", r.Method, "path", r.URL.Path, "duration_ms", time.Since(started).Milliseconds())
	})
}

func recoverer(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				logger.Error("panic recovered", "error", recovered)
				problem(w, http.StatusInternalServerError, "internal error", "The request could not be completed.")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func valueOr(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
