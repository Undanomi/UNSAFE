package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/Undanomi/SLSG/build_server/internal/config"
	"github.com/Undanomi/SLSG/build_server/internal/postgres"
	"github.com/Undanomi/SLSG/build_server/internal/worker"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	cfg, err := config.WorkerFromEnv()
	if err != nil {
		logger.Error("configuration error", "error", err)
		os.Exit(1)
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	store, err := postgres.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("database connection failed", "error", err)
		os.Exit(1)
	}
	defer store.Close()
	if err := store.Migrate(ctx); err != nil {
		logger.Error("database migration failed", "error", err)
		os.Exit(1)
	}
	logger.Info("build worker started", "worker_id", cfg.WorkerID)
	if err := worker.New(cfg, store, logger).Run(ctx); err != nil {
		logger.Error("worker stopped unexpectedly", "error", err)
		os.Exit(1)
	}
}
