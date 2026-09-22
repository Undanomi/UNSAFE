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
builder/launchers/      end-user QEMU launchers and connection guides
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
`builder/base_images/debian-<version>-amd64.qcow2`. For example, Debian 13.7.0
uses `debian-13.7.0-amd64.qcow2`. A missing `target_os` defaults to Debian 13.7.0.

The current Packer communicator supports Debian images. Put every Debian version
you intend to build under `builder/base_images/`, then start the stack:

Copy the environment template, then fill the blank `INTERNAL_API_TOKEN` and
`BUILD_POSTGRES_PASSWORD` values with independent random values. The API token
must be at least 32 characters and identical to the AI server's
`BUILD_SERVER_TOKEN`. There are no built-in secret fallbacks.

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

Changing `POSTGRES_PASSWORD` does not update a role in an existing PostgreSQL
data volume. For an existing deployment, change the database role password
first, then update `BUILD_POSTGRES_PASSWORD` and restart the services.

The build server is an internal service. Its port is exposed only to the Compose
network and the AI server is its sole application-level caller. Users create and
inspect machines through the AI server API, then download the completed distribution with:

```sh
curl -L -OJ \
  http://localhost:8000/v1/sessions/{session_id}/download \
  -H 'X-Authenticated-User-ID: user-123'

unzip ARTIFACT_ID.zip
cd slsg-machine
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
`provisioner` user password with a cryptographically random value. A completed build's
authenticated `GET /v1/builds/{build_id}` response includes that value in
`machine_password`. The AI server copies it to its session's `machine_access`
field. Treat both fields as secrets and do not write them to logs.

The worker also installs `slsg-login-banner.service` as the final guest
customization. It waits for DHCP and writes every global IPv4 address to
`/etc/issue`, so the target address is visible before console login. End-user
launchers and their platform-specific connection guides are copied from
`builder/launchers/` beside `image.qcow2`. The worker packages all of these files
under a top-level `slsg-machine/` directory in the single
`<artifact_id>.zip` distribution artifact, then removes the individual files
from the public artifact directory.
When the worker starts, it also converts registered legacy `tar.zst` artifacts
to ZIP, keeps the existing artifact ID, updates the stored size and SHA-256,
and removes the old file only after the metadata update succeeds.
