"""Serial CPU inference shared by all Streamlit sessions and the workload CLI."""
import os
import threading
import time
from .inputs import InputError, decode_image, read_upload

MODEL_ID = 'Salesforce/blip-image-captioning-base'
MODEL_REVISION = '82a37760796d32b1411fe092ab5d4e227313294b'


class CaptionService:
    def __init__(self, metrics):
        self.metrics = metrics
        self.lock = threading.Lock()
        self.model = None
        self.processor = None

    def load(self):
        if self.model is not None:
            return
        started = time.perf_counter()
        self.metrics.loading.set(1)
        try:
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration
            torch.set_num_threads(max(1, int(os.getenv('CPU_THREADS', '2'))))
            processor = BlipProcessor.from_pretrained(MODEL_ID, revision=MODEL_REVISION, use_fast=False)
            model = BlipForConditionalGeneration.from_pretrained(MODEL_ID, revision=MODEL_REVISION, use_safetensors=False)
            model.to('cpu').eval()
            self.processor, self.model = processor, model
            self.metrics.model_bytes.set(sum(p.numel() * p.element_size() for p in model.parameters()))
            self.metrics.load_seconds.set(time.perf_counter() - started)
            self.metrics.ready.set(1)
        except Exception:
            self.metrics.ready.set(0)
            raise
        finally:
            self.metrics.loading.set(0)

    def infer(self, image):
        import torch
        inputs = self.processor(images=image, return_tensors='pt').to('cpu')
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=40, num_beams=1, do_sample=False)
        return self.processor.decode(output[0], skip_special_tokens=True).strip()

    def process(self, name, data, mode, session_id, progress=None):
        m = self.metrics
        started = time.perf_counter()
        status, remaining = 'error', 0
        m.active.labels(mode).inc()
        m.clients.labels(mode, m.client_bucket(session_id)).inc()
        m.upload.labels(mode).observe(len(data))
        m.upload_total.labels(mode).inc(len(data))
        try:
            try:
                items, skipped = read_upload(name, data, mode)
            except InputError:
                m.errors.labels(mode, 'validation').inc()
                raise
            remaining = len(items)
            m.pending.labels(mode).inc(remaining)
            rows = []
            for index, (filename, raw) in enumerate(items):
                row = {'filename': filename, 'caption': '', 'status': 'error', 'error': ''}
                try:
                    image = decode_image(raw)
                except InputError as exc:
                    row['error'] = str(exc)
                    m.errors.labels(mode, 'decode').inc()
                else:
                    wait_start = time.perf_counter()
                    with self.lock:
                        m.wait.labels(mode).observe(time.perf_counter() - wait_start)
                        try:
                            self.load()
                        except Exception:
                            row['error'] = 'Model could not load. Check server logs and download access.'
                            m.errors.labels(mode, 'model_load').inc()
                            import logging
                            logging.exception('Model load failed')
                        else:
                            infer_start = time.perf_counter()
                            m.inference.inc()
                            try:
                                row['caption'] = self.infer(image)
                                row['status'] = 'success'
                            except Exception:
                                row['error'] = 'Inference failed. Check server logs.'
                                m.errors.labels(mode, 'inference').inc()
                                import logging
                                logging.exception('Inference failed')
                            finally:
                                m.inference.dec()
                                m.latency.labels(mode).observe(time.perf_counter() - infer_start)
                m.images.labels(mode, row['status']).inc()
                m.pending.labels(mode).dec()
                remaining -= 1
                rows.append(row)
                if progress:
                    progress((index + 1) / len(items))
            successes = sum(row['status'] == 'success' for row in rows)
            status = 'success' if successes == len(rows) else 'partial' if successes else 'error'
            return rows, skipped
        finally:
            if remaining:
                m.pending.labels(mode).dec(remaining)
            m.requests.labels(mode, status).inc()
            m.active.labels(mode).dec()
            elapsed = time.perf_counter() - started
            m.job_time.labels(mode).observe(elapsed)
            m.observed_seconds.labels(mode).inc(elapsed)
