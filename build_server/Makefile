.PHONY: test build run

test:
	go test ./...

build:
	go build ./cmd/server ./cmd/worker

run:
	docker compose up --build
