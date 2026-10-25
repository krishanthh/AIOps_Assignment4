#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for name in streamlit prometheus alertmanager node-exporter alert-receiver; do
  pidfile=".runtime/$name.pid"
  if [[ -f "$pidfile" ]]; then
    task_pid="$(cat "$pidfile")"
    # Check the recorded process still belongs to this assignment before killing.
    if [[ -r "/proc/$task_pid/cwd" || -d "/proc/$task_pid" ]]; then
      task_cwd="$(readlink "/proc/$task_pid/cwd" || true)"
      if [[ "$task_cwd" == "$PWD" ]]; then kill "$task_pid" 2>/dev/null || true; fi
    fi
    rm "$pidfile"
  fi
done
