"""Bounded in-memory ZIP reading: never extract user-supplied paths."""
from io import BytesIO
from pathlib import PurePosixPath
import warnings
import zipfile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 50 * 1024 * 1024
MAX_IMAGE = 15 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
MAX_IMAGES = 100
MAX_PIXELS = 20_000_000
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class InputError(ValueError):
    pass


def decode_image(data):
    if len(data) > MAX_IMAGE:
        raise InputError('Image exceeds 15 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise InputError('Image exceeds 20 megapixels.')
                image.load()
                rgb = ImageOps.exif_transpose(image).convert('RGB')
                rgb.thumbnail((1024, 1024))
                return rgb.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InputError('Invalid, corrupt, or oversized image.') from exc


def read_upload(name, data, mode):
    if not data or len(data) > MAX_UPLOAD:
        raise InputError('Upload must be nonempty and at most 50 MiB.')
    if mode == 'single':
        return [(PurePosixPath(name).name, data)], 0
    if mode != 'bulk':
        raise InputError('Unknown mode.')
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 1000:
                raise InputError('ZIP has too many entries (maximum 1000).')
            images, total, skipped = [], 0, 0
            for member in members:
                path = PurePosixPath(member.filename)
                if member.is_dir():
                    continue
                if path.is_absolute() or '..' in path.parts or '\\' in member.filename:
                    raise InputError('ZIP contains an unsafe path.')
                if member.flag_bits & 1:
                    raise InputError('Encrypted ZIP files are unsupported.')
                total += member.file_size
                if total > MAX_EXPANDED:
                    raise InputError('Expanded ZIP exceeds 100 MiB.')
                if path.suffix.lower() not in EXTENSIONS or '__MACOSX' in path.parts:
                    skipped += 1
                    continue
                if len(images) >= MAX_IMAGES:
                    raise InputError('ZIP may contain at most 100 images.')
                if member.file_size > MAX_IMAGE:
                    raise InputError('An image in the ZIP exceeds 15 MiB.')
                if member.file_size > max(1, member.compress_size) * 200:
                    raise InputError('ZIP compression ratio exceeds 200:1.')
                images.append((member.filename, archive.read(member)))
            if not images:
                raise InputError('ZIP contains no supported images.')
            return images, skipped
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
        raise InputError('Invalid or unsupported ZIP archive.') from exc
