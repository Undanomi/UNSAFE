FROM debian:12-slim

ARG PACKER_VERSION=1.11.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      qemu-system-x86 \
      qemu-utils \
      unzip \
      xorriso \
    && curl -fsSL "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_amd64.zip" -o /tmp/packer.zip \
    && unzip /tmp/packer.zip -d /usr/local/bin \
    && rm -rf /var/lib/apt/lists/* /tmp/packer.zip

WORKDIR /work
ENTRYPOINT ["packer"]