FROM golang:1.25-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/worker ./cmd/worker

FROM debian:12-slim AS packer
ARG PACKER_VERSION=1.11.2
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && curl -fsSL "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_amd64.zip" -o /tmp/packer.zip \
    && unzip /tmp/packer.zip -d /usr/local/bin \
    && rm -rf /var/lib/apt/lists/* /tmp/packer.zip
COPY builder/packer /opt/slsg/packer
COPY builder/launchers /opt/slsg/launchers
RUN packer init /opt/slsg/packer/build.pkr.hcl

FROM gcr.io/distroless/static-debian12:nonroot AS server
COPY --from=build /out/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]

FROM debian:12-slim AS worker
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates qemu-system-x86 qemu-utils tar xorriso zstd \
    && rm -rf /var/lib/apt/lists/*
COPY --from=packer /usr/local/bin/packer /usr/local/bin/packer
COPY --from=packer /root/.config/packer/plugins /opt/packer/plugins
COPY --from=packer /opt/slsg /opt/slsg
COPY --from=build /out/worker /worker
RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /var/lib/slsg/builds /var/lib/slsg/scenarios \
    && chown -R worker:worker /var/lib/slsg
ENV PACKER_PLUGIN_PATH=/opt/packer/plugins
USER worker
ENTRYPOINT ["/worker"]
