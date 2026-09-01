# SLSG Build Service

The build service accepts asynchronous REST requests and stores build state in
PostgreSQL. Workers claim jobs from the same database with
`FOR UPDATE SKIP LOCKED`, run Packer, and publish artifacts atomically.

## Layout

```text
cmd/server/             REST API process
cmd/worker/             Packer worker process
internal/httpapi/       HTTP transport and authentication boundary
internal/postgres/      build repository and PostgreSQL job queue
internal/worker/        isolated workspace and Packer orchestration
builder/packer/         controlled Packer template
builder/base_images/    base VM images (not committed)
data/scenarios/         local-development scenario inputs (not committed)
```

Scenario source is uploaded as a ZIP file and extracted by the API into a
build-specific internal path:

```text
/var/lib/slsg/scenarios/uploads/{build_id}/source/
```

The worker derives this path from the generated build ID; callers cannot supply
a filesystem path. The archive must contain `build.sh`, either at its root, in
`contents/`, or within three levels of the root.

## Local development

KVM must be available at `/dev/kvm`. The worker reads `target_os` from
`contents/scenario_manifest.json` and selects a base image named
`builder/base_images/ubuntu-<version>-server.qcow2`. For example, Ubuntu 24.04
uses `ubuntu-24.04-server.qcow2`. A missing `target_os` defaults to Ubuntu 26.04.

The current Packer communicator supports Ubuntu images. Put every Ubuntu version
you intend to build under `builder/base_images/`, then start the stack:

```sh
cp .env.example .env
docker compose up --build
```

Set `KVM_GID` in `.env` to the numeric group of the host KVM device before
starting the worker:

```sh
stat -c '%g' /dev/kvm
```

The default is `993`, matching the development host used by this repository.

The build server is an internal service. Its port is exposed only to the Compose
network and the AI server is its sole application-level caller. Users create and
inspect machines through the AI server API, then download a completed image with:

```sh
curl -L -o image.qcow2 \
  http://localhost:8000/v1/sessions/{session_id}/download \
  -H 'X-Authenticated-User-ID: user-123'
```

Archives are limited to 64 MiB compressed, 512 MiB expanded, 100 MiB per file,
and 10,000 entries. Absolute paths, parent traversal, symbolic links, and
non-regular files are rejected.

The AI server authenticates the user context and calls this API with a service
token. Production deployments should replace the development token with a
short-lived, audience-restricted internal JWT or enforce equivalent authentication
at the service boundary.

## API

The internal contract used by the AI server is documented in
[`api/openapi.yaml`](api/openapi.yaml). Important operations are:

- `POST /v1/builds`
- `GET /v1/builds/{build_id}`
- `POST /v1/builds/{build_id}/cancel`
- `POST /v1/builds/{build_id}/retry`
- `GET /v1/builds/{build_id}/events?after={event_id}`
- `GET /v1/builds/{build_id}/logs/packer`
- `GET /v1/builds/{build_id}/artifacts`
- `GET /v1/builds/{build_id}/artifacts/{artifact_id}/content`

After the scenario `build.sh` succeeds, the worker replaces the base image's
`ubuntu` user password with a cryptographically random value. A completed build's
authenticated `GET /v1/builds/{build_id}` response includes that value in
`machine_password`. The AI server copies it to its session's `machine_access`
field. Treat both fields as secrets and do not write them to logs.
