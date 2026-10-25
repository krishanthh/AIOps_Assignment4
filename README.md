# DA3408 Assignment 4 — CPU captioning observability

Krishanthh Mohan · DA24B044

The Streamlit application generates real BLIP captions for a single image or a ZIP of images. Prometheus collects application and native host metrics; Grafana displays health, traffic, latency and resource correlation with five-second refresh. Alertmanager delivers local webhook notifications.

## Submission contents

- `app.py`, `captioning/`: CPU model inference, validated uploads, bulk error recovery, CSV export and instrumentation.
- `prometheus.yml`, `monitoring/`: scrape configuration, alert rules and local Alertmanager routing.
- `grafana/dashboards/caption-observability.json`: required dashboard export. `grafana/provisioning/` supplies the datasource and dashboard provisioning.
- `scripts/`: only dependency/tool installation, service startup/shutdown and the local alert receiver.
- `evidence/`: final executed outcomes, actual bulk captions, dashboard-query results, alert notifications and the public example image.
- `AI_DISCLOSURE.md`: assistance and PromQL attribution.

The proof video is outside this folder: `../assignment videos/Assignment_4_Captioning_and_Monitoring_Demo.mp4`. It includes real single-image and bulk uploads, CSV export, **100 seconds of live Grafana at five-second refresh**, and Prometheus target health.

## Install and start

Use Linux ARM64 or AMD64, Docker, `uv`, and Python 3.10–3.12. The validated environment used Python 3.10.21, CPU PyTorch 2.8.0 and Transformers 4.57.1. Local environments, binaries, runtime stores and model weights are not part of the submission; installation recreates them.

From this folder:

```bash
uv python install 3.10.21
PYTHON_BIN="$(uv python find 3.10.21)" bash scripts/install_python.sh
python3 scripts/install_tools.py
bash scripts/start_native.sh
bash scripts/start_grafana.sh
```

The tool installer selects the correct native Linux architecture and verifies official SHA256 checksums. Prometheus 3.7.3, Alertmanager 0.28.1 and node_exporter 1.10.2 run natively. Grafana Enterprise 12.2.1 uses Docker on port 3000, with initial credentials `admin` / `admin`. The script reuses an existing container named `grafana`.

Ports 8000 and 9090 overlap with the separate BrainScope project: stop that stack before running this assignment. If tools and dependencies have already been installed, use only the two startup commands. To stop the native services, run `bash scripts/stop_native.sh`.

| Service | Address |
|---|---|
| Streamlit | http://localhost:8501 |
| Grafana | http://localhost:3000/d/caption-observability |
| Prometheus targets | http://localhost:9090/targets |
| Prometheus alerts | http://localhost:9090/alerts |
| Alertmanager | http://localhost:9093 |
| App metrics | http://localhost:8000/metrics |
| Native node metrics | http://localhost:9100/metrics |

Visit Streamlit to initialize the metrics endpoint. First inference downloads the pinned `Salesforce/blip-image-captioning-base` revision `82a37760796d32b1411fe092ab5d4e227313294b` (about 1 GB). The app explicitly uses CPU, two inference threads and a shared model lock. Once cached, `HF_HUB_OFFLINE=1 bash scripts/start_native.sh` avoids network lookups.

The launcher uses independent process sessions so terminal closure does not stop the services. Runtime data is regenerated under `.runtime/`, including `prometheus-current` and `alertmanager-current`. Prometheus listens on `0.0.0.0:9090` so container Grafana can access it using `host.docker.internal`; the other native services bind to loopback. Use this configuration on the local coursework machine.

## Use the application

Choose **Single image**, upload a JPG/PNG/WEBP/BMP and select **Generate caption**. The provided [example image](evidence/sample-image.jpg) comes from the [BLIP model-card example](https://huggingface.co/Salesforce/blip-image-captioning-base).

Choose **Bulk ZIP**, upload an archive and select **Process ZIP**. Non-image entries are skipped. A corrupt image produces an error row while valid images continue. Results remain available for CSV download. Limits are 50 MiB compressed upload, 100 images, 15 MiB/image, 100 MiB declared expanded size, 20 megapixels/image, 1,000 entries and a maximum compression ratio of 200:1. ZIP paths are never extracted to disk.

## Metric logic and dashboard

- **Counters:** image/job outcomes, errors, uploaded bytes and bounded hashed client cohorts. Sixteen cohorts track session metadata without exporting raw identifiers.
- **Gauges:** active jobs, pending images, model readiness/loading, process CPU/RAM and model bytes.
- **Histograms:** inference latency and model-lock waiting time; histogram buckets support estimated p50/p95 latency.
- **Summaries:** job duration and upload size expose `_sum` and `_count`. Separate counters supply cumulative `_total` values; Python Summary does not emit `_total` itself.

Illustrative arithmetic, not measured results: 12 successful images over 120 seconds gives **6 images/minute**. A Summary increase of 48 seconds across four jobs gives **12 seconds/job**. Host CPU is `100 × (1 − mean idle-time rate)`; RAM use is `100 × (1 − available / total)`. Histogram percentiles are estimates within bucket boundaries, not exact individual request times. For 100 observations, cumulative counts of 90 at 10 seconds and 100 at 20 seconds give an interpolated p95 of `10 + (95 − 90) / (100 − 90) × 10 = 15 seconds`.

Read Grafana from health to traffic, latency, hardware and error/client diagnostics. Blue/orange mode colors, line styles, visible points, legends, linear axes, explicit units and panel descriptions preserve the plots' meaning across media. All panels share a time axis. Run a real bulk upload and compare active/pending work with CPU and RAM; cold-start memory must be distinguished from steady-state inference. AI generation prompts remain embedded in the dashboard and alert-rule configuration.

## Executed outcome

The final recorded bulk run produced **12 captions, one corrupt-image error and one skipped text file**. All **36 dashboard expressions** and **four scrape targets** were checked against live services; Grafana datasource health was OK. The final evidence is [final-validation.json](evidence/final-validation.json), [actual CSV](evidence/final-browser-captions.csv) and [stack-validation.json](evidence/stack-validation.json).

Optional tests, browser-check scripts, dashboard-generation helpers and development notes are archived outside the submission under `../assignment support/`.
