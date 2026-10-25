#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Publish the course-specified port; host-gateway connects to native Prometheus.
if docker container inspect grafana >/dev/null 2>&1; then
  docker start grafana
else
  docker pull grafana/grafana-enterprise:12.2.1
  docker run -d -p 3000:3000 --name=grafana --add-host=host.docker.internal:host-gateway \
    --label da3408.assignment=4 \
    -e GF_DASHBOARDS_MIN_REFRESH_INTERVAL=5s \
    -v "$TASK_ROOT/grafana/provisioning:/etc/grafana/provisioning:ro" \
    -v "$TASK_ROOT/grafana/dashboards:/var/lib/grafana/dashboards:ro" \
    -v da3408-a4-grafana:/var/lib/grafana \
    grafana/grafana-enterprise:12.2.1
fi
