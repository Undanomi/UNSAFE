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

KVM must be available at `/dev/kvm`. Put the base image at
`builder/base_images/ubuntu-26.04-server.qcow2`, then start the stack:

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

Create a build:

```sh
curl -i http://localhost:8080/v1/builds \
  -H 'Authorization: Bearer local-development-token' \
  -H 'X-Authenticated-User-ID: user-123' \
  -H 'Idempotency-Key: request-001' \
  -F 'scenario_id=scenario-1' \
  -F 'scenario_version_id=v1' \
  -F 'source=@scenario-source.zip;type=application/zip'
```

Archives are limited to 64 MiB compressed, 512 MiB expanded, 100 MiB per file,
and 10,000 entries. Absolute paths, parent traversal, symbolic links, and
non-regular files are rejected.

The BFF must authenticate the end user and call this API with a service token.
Production deployments should replace the development token with a short-lived,
audience-restricted internal JWT or enforce equivalent authentication at the
service proxy. TLS is expected to terminate at the internal ingress/proxy.

## API

The contract is documented in [`api/openapi.yaml`](api/openapi.yaml). Important
operations are:

- `POST /v1/builds`
- `GET /v1/builds/{build_id}`
- `POST /v1/builds/{build_id}/cancel`
- `POST /v1/builds/{build_id}/retry`
- `GET /v1/builds/{build_id}/events?after={event_id}`
- `GET /v1/builds/{build_id}/artifacts`
- `GET /v1/builds/{build_id}/artifacts/{artifact_id}/content`
