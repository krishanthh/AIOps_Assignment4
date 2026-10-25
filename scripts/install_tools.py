#!/usr/bin/env python3
"""Download pinned official archives, verify SHA256, extract locally; no root needed."""
import hashlib
import json
import platform
from pathlib import Path
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = {'prometheus': '3.7.3', 'alertmanager': '0.28.1', 'node_exporter': '1.10.2'}
ARCH = {'aarch64': 'arm64', 'arm64': 'arm64', 'x86_64': 'amd64'}.get(platform.machine())
if platform.system() != 'Linux' or not ARCH:
    raise SystemExit('This installer supports Linux ARM64 and AMD64.')
target = ROOT / '.tools'
target.mkdir(exist_ok=True)
manifest = {}
for name, version in VERSIONS.items():
    stem = f'{name}-{version}.linux-{ARCH}'
    filename = stem + '.tar.gz'
    base = f'https://github.com/prometheus/{name}/releases/download/v{version}/'
    archive = target / filename
    print(f'Downloading {filename}', flush=True)
    checksums = urllib.request.urlopen(base + 'sha256sums.txt').read().decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1].lstrip('*') == filename)
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        urllib.request.urlretrieve(base + filename, archive)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'Checksum mismatch: {filename}')
    with tarfile.open(archive) as bundle:
        bundle.extractall(target, filter='data')
    link = target / name
    if link.is_symlink():
        link.unlink()
    link.symlink_to(stem, target_is_directory=True)
    manifest[name] = {'version': version, 'architecture': ARCH, 'url': base + filename, 'sha256': actual}
(ROOT / 'evidence' / 'tool-downloads.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Verified native binaries installed in', target)
