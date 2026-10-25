"""One registry per application process; no raw IPs or unbounded session labels."""
import hashlib
import os
import threading
import time

import psutil
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Summary, start_http_server
from prometheus_client import GCCollector, PlatformCollector, ProcessCollector


class Metrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        ProcessCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        def metric(kind, name, doc, labels=(), **kw):
            return kind('caption_' + name, doc, labels, registry=self.registry, **kw)
        self.images = metric(Counter, 'images_total', 'Images attempted by mode and outcome.', ['mode', 'status'])
        self.requests = metric(Counter, 'requests_total', 'Submitted jobs by mode and outcome.', ['mode', 'status'])
        self.clients = metric(Counter, 'client_requests_total', 'Jobs by bounded hashed session cohort.', ['mode', 'client_bucket'])
        self.errors = metric(Counter, 'errors_total', 'Failures by bounded reason.', ['mode', 'reason'])
        self.active = metric(Gauge, 'active_requests', 'Jobs running or waiting for the CPU model.', ['mode'])
        self.pending = metric(Gauge, 'pending_images', 'Images remaining in accepted jobs.', ['mode'])
        self.inference = metric(Gauge, 'inference_active', 'Images currently inside model inference.')
        self.ready = metric(Gauge, 'model_ready', 'One after CPU model load; zero before or after load failure.')
        self.loading = metric(Gauge, 'model_loading', 'One while loading model weights.')
        self.load_seconds = metric(Gauge, 'model_load_seconds', 'Duration of latest successful model load in seconds.')
        self.model_bytes = metric(Gauge, 'model_parameter_bytes', 'CPU model parameter storage in bytes (not total RSS).')
        self.rss = metric(Gauge, 'process_memory_bytes', 'Application process resident memory, bytes.')
        self.cpu = metric(Gauge, 'process_cpu_percent', 'Process CPU percent; 100 percent equals one core.')
        self.heartbeat = metric(Gauge, 'heartbeat_timestamp_seconds', 'Last resource sampler heartbeat, Unix seconds.')
        self.latency = metric(Histogram, 'inference_seconds', 'Inference duration including failures, excluding lock wait.', ['mode'], buckets=(.1,.25,.5,1,2,5,10,20,30,60,120,300))
        self.wait = metric(Histogram, 'queue_wait_seconds', 'Time waiting for the shared CPU model lock.', ['mode'], buckets=(.01,.1,1,5,10,30,60,120,300))
        self.job_time = metric(Summary, 'job_duration_seconds', 'End-to-end submitted job duration, including validation.', ['mode'])
        self.upload = metric(Summary, 'upload_bytes', 'Submitted upload size in bytes.', ['mode'])
        self.observed_seconds = metric(Counter, 'observed_job_seconds_total', 'Cumulative observed job seconds; paired with Summary count.', ['mode'])
        self.upload_total = metric(Counter, 'uploaded_bytes_total', 'Cumulative bytes submitted.', ['mode'])
        for mode in ('single', 'bulk'):
            self.active.labels(mode).set(0)
            self.pending.labels(mode).set(0)
            self.latency.labels(mode)
            self.wait.labels(mode)
            self.job_time.labels(mode)
            self.upload.labels(mode)
            self.observed_seconds.labels(mode)
            self.upload_total.labels(mode)
            for status in ('success', 'partial', 'error'):
                self.requests.labels(mode, status)
            for status in ('success', 'error'):
                self.images.labels(mode, status)
        self.ready.set(0)
        self.loading.set(0)
        self.inference.set(0)

    def client_bucket(self, session_id):
        return str(int.from_bytes(hashlib.sha256(session_id.encode()).digest()[:2], 'big') % 16)

    def serve(self, port=None):
        server, thread = start_http_server(port or int(os.getenv('METRICS_PORT', '8000')), addr='127.0.0.1', registry=self.registry)
        def sample():
            process = psutil.Process()
            process.cpu_percent()
            while True:
                self.rss.set(process.memory_info().rss)
                self.cpu.set(process.cpu_percent())
                self.heartbeat.set(time.time())
                time.sleep(2)
        threading.Thread(target=sample, daemon=True).start()
        return server, thread
