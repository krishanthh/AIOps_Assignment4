"""Run with: .venv/bin/streamlit run app.py"""
import csv
import io
import uuid
import streamlit as st
from captioning.inputs import InputError
from captioning.metrics import Metrics
from captioning.service import CaptionService

st.set_page_config(page_title='Caption Lab · CPU observability', page_icon='📷', layout='wide')

@st.cache_resource
def resources():
    metrics = Metrics()
    server = metrics.serve()
    return CaptionService(metrics), server

service, _server = resources()
if 'client_id' not in st.session_state:
    st.session_state.client_id = uuid.uuid4().hex

st.title('Caption Lab')
st.caption('CPU image captioning · Single images and bulk ZIPs · Prometheus + Grafana')
with st.sidebar:
    st.header('Run controls')
    choice = st.radio('Processing mode', ['Single image', 'Bulk ZIP'])
    st.info('BLIP base runs on CPU with two threads by default. The first valid image downloads and loads the model; allow extra time.')
    st.markdown('[Open monitoring dashboard](http://localhost:3000/d/caption-observability)')
    st.caption('Client tracking uses 16 hashed session cohorts. Raw IPs and session IDs are never exported.')
mode = 'single' if choice == 'Single image' else 'bulk'
st.subheader('Describe an image' if mode == 'single' else 'Caption a collection')
st.write('Upload a JPG, PNG, WEBP, or BMP.' if mode == 'single' else 'Upload a ZIP with up to 100 images. Files are processed one at a time to bound CPU and memory use.')
st.caption('Limits: 50 MiB upload · 15 MiB/image · 20 megapixels/image · 100 MiB expanded ZIP. Invalid images get individual error rows.')
def clear_results():
    st.session_state.pop('result_' + mode, None)
    st.session_state.pop('skipped_' + mode, None)

upload = st.file_uploader('Image' if mode == 'single' else 'ZIP archive', type=['jpg','jpeg','png','webp','bmp'] if mode == 'single' else ['zip'], key=mode, on_change=clear_results)
if st.button('Generate caption' if mode == 'single' else 'Process ZIP', type='primary', disabled=upload is None):
    progress = st.progress(0.0, text='Processing on CPU…')
    try:
        with st.spinner('Generating captions…'):
            rows, skipped = service.process(upload.name, upload.getvalue(), mode, st.session_state.client_id, progress.progress)
        st.session_state['result_' + mode] = rows
        st.session_state['skipped_' + mode] = skipped
    except InputError as exc:
        st.error(str(exc))
    except Exception:
        import logging
        logging.exception('Unexpected job failure')
        st.error('The job failed. Check the server log, then retry.')
    finally:
        progress.empty()
rows = st.session_state.get('result_' + mode)
if rows:
    success = sum(row['status'] == 'success' for row in rows)
    st.metric('Images captioned', f'{success} / {len(rows)}')
    if mode == 'single' and upload and rows[0]['status'] == 'success':
        st.image(upload, width=400)
        if rows[0]['caption']:
            st.success(rows[0]['caption'])
    st.dataframe(rows, hide_index=True, width='stretch')
    if st.session_state.get('skipped_' + mode):
        st.caption(f"Skipped {st.session_state['skipped_' + mode]} non-image entries.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['filename', 'caption', 'status', 'error'])
    writer.writeheader()
    # Escape spreadsheet formula prefixes in user-supplied filenames and generated text.
    writer.writerows({k: "'" + v if v.startswith(('=', '+', '-', '@')) else v for k, v in row.items()} for row in rows)
    st.download_button('Download captions as CSV', output.getvalue(), 'captions.csv', 'text/csv')
