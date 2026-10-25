#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime
export HF_HOME="$PWD/.cache/huggingface"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
.tools/prometheus/promtool check config prometheus.yml
.tools/alertmanager/amtool check-config monitoring/alertmanager.yml
start() {
  local name="$1"
  shift
  .venv/bin/python - "$name" "$@" <<'PY_START'
import os
from pathlib import Path
import subprocess
import sys
name, *command = sys.argv[1:]
root = Path.cwd()
pidfile = root / '.runtime' / (name + '.pid')
if pidfile.exists():
    try:
        pid = int(pidfile.read_text())
        os.kill(pid, 0)
        if Path(f'/proc/{pid}/cwd').resolve() == root:
            print(name + ' already running')
            raise SystemExit(0)
    except (ValueError, OSError):
        pass
with (root / '.runtime' / (name + '.log')).open('w') as stream:
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                             stderr=subprocess.STDOUT, start_new_session=True)
pidfile.write_text(str(child.pid))
PY_START
}
start alert-receiver .venv/bin/python scripts/alert_receiver.py
start node-exporter .tools/node_exporter/node_exporter --web.listen-address=127.0.0.1:9100
start alertmanager .tools/alertmanager/alertmanager --config.file=monitoring/alertmanager.yml --storage.path=.runtime/alertmanager-current --web.listen-address=127.0.0.1:9093 --cluster.listen-address=
start prometheus .tools/prometheus/prometheus --config.file=prometheus.yml --storage.tsdb.path=.runtime/prometheus-current --storage.tsdb.retention.time=7d --web.listen-address=0.0.0.0:9090
start streamlit .venv/bin/streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --server.maxUploadSize=50
sleep 2
for name in alert-receiver node-exporter alertmanager prometheus streamlit; do
  kill -0 "$(cat ".runtime/$name.pid")" || { cat ".runtime/$name.log"; exit 1; }
done
echo 'Open http://localhost:8501 (app) and http://localhost:3000/d/caption-observability (Grafana).'
echo 'Visit the app once to initialize its /metrics server on port 8000.'
