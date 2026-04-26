FROM ubuntu:22.04

LABEL maintainer="network-testbed"
LABEL description="Network node image with routing and traffic control tools"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    net-tools \
    iptables \
    tcpdump \
    traceroute \
    curl \
    wget \
    nano \
    procps \
    inetutils-traceroute \
    netcat-openbsd \
    iperf3 \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Enable IP forwarding at runtime via entrypoint
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Prometheus node exporter for basic metrics
ARG NODE_EXPORTER_VERSION=1.7.0
RUN wget -q https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz -O /tmp/ne.tar.gz || true \
    && tar -xzf /tmp/ne.tar.gz -C /usr/local/bin --strip-components=1 node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter 2>/dev/null || true \
    && rm -f /tmp/ne.tar.gz

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sleep", "infinity"]
