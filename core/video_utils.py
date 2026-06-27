"""
Video processing pipeline for FaceChan.

Handles short user-uploaded clips (MP4 and WebM only).
Mirrors image_utils.py in structure and naming conventions.

Processing steps:
  1. Size check against SiteSettings.max_video_size_mb
  2. Format validation — MP4 and WebM only
  3. Duration check against SiteSettings.max_video_duration_seconds
  4. Metadata strip + re-encode via FFmpeg (subprocess call)
  5. Thumbnail extracted from first frame → WebP via Pillow
  6. Perceptual hash computed on first frame for CSAM checkpoint

FFmpeg is required. Add to Dockerfile:
  RUN apt-get install -y --no-install-recommends ffmpeg

R2 swap point is at the bottom of this file, same as image_utils.py.
"""

import io
import logging
import os
import subprocess
import tempfile
import uuid

from PIL import Image

logger = logging.getLogger('facechan')

ALLOWED_MIME_TYPES = {'video/mp4', 'video/webm'}
ALLOWED_EXTENSIONS = {'.mp4', '.webm'}

THUMBNAIL_WIDTH  = 320
THUMBNAIL_HEIGHT = 180
THUMBNAIL_QUALITY = 70

# FFmpeg output codec settings
# MP4  → H.264 video / AAC audio (universally supported)
# WebM → VP9 video / Opus audio (open, efficient)
FFMPEG_CODEC_MAP = {
    '.mp4':  ['-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
              '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart'],
    '.webm': ['-c:v', 'libvpx-vp9', '-crf', '33', '-b:v', '0',
              '-c:a', 'libopus', '-b:a', '96k'],
}


def _ffmpeg_available():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _get_video_duration(path):
    """Return duration in seconds via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def process_video(upload_file, max_upload_bytes, max_duration_seconds, allow_sound=True):
    """
    Accept a Django InMemoryUploadedFile or similar video upload.

    allow_sound: if False, audio stream is stripped entirely during encode.

    Returns a dict:
        {
            'video_bytes': bytes,        # re-encoded video
            'extension':   str,          # '.mp4' or '.webm'
            'content_type': str,         # 'video/mp4' or 'video/webm'
            'duration':    float,        # seconds
        }

    Raises ValueError with a user-facing message on any validation failure.
    FFmpeg errors also raise ValueError.
    """
    if not _ffmpeg_available():
        raise ValueError('Video processing is not available on this server.')

    # ── Size check ────────────────────────────────────────────────────────────
    if upload_file.size > max_upload_bytes:
        max_mb = max_upload_bytes // 1024 // 1024
        raise ValueError(f'Video too large (max {max_mb}MB).')

    # ── Extension / MIME check ────────────────────────────────────────────────
    original_name = getattr(upload_file, 'name', '') or ''
    ext = os.path.splitext(original_name)[1].lower()
    content_type = getattr(upload_file, 'content_type', '') or ''

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError('Only MP4 and WebM videos are accepted.')
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise ValueError('Only MP4 and WebM videos are accepted.')

    # ── Write upload to temp file for ffprobe/ffmpeg ──────────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path  = os.path.join(tmpdir, f'input{ext}')
        output_path = os.path.join(tmpdir, f'output{ext}')

        with open(input_path, 'wb') as f:
            for chunk in upload_file.chunks():
                f.write(chunk)

        # ── Duration check ────────────────────────────────────────────────────
        duration = _get_video_duration(input_path)
        if duration is None:
            raise ValueError('Could not read video file. Is it a valid MP4 or WebM?')
        if max_duration_seconds and duration > max_duration_seconds:
            max_mins = max_duration_seconds // 60
            raise ValueError(f'Video too long (max {max_mins} minutes).')

        # ── FFmpeg re-encode: strip metadata + normalise ──────────────────────
        codec_args = FFMPEG_CODEC_MAP[ext]
        audio_map = ['-map', '0:a:0?'] if allow_sound else ['-an']
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-map_metadata', '-1',   # strip ALL metadata (EXIF, GPS, encoder info)
            '-map', '0:v:0',         # keep first video stream only
        ] + audio_map + codec_args + [output_path]

        try:
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                timeout=300,  # 5 min max for encode
            )
            if result.returncode != 0:
                logger.error(
                    'FFmpeg encode failed: %s',
                    result.stderr.decode('utf-8', errors='replace')
                )
                raise ValueError('Video processing failed. Please try a different file.')
        except subprocess.TimeoutExpired:
            raise ValueError('Video processing timed out. Please upload a shorter clip.')

        with open(output_path, 'rb') as f:
            video_bytes = f.read()

    content_type_out = 'video/mp4' if ext == '.mp4' else 'video/webm'
    return {
        'video_bytes':  video_bytes,
        'extension':    ext,
        'content_type': content_type_out,
        'duration':     duration,
    }


def extract_video_thumbnail(video_file_path_or_bytes, ext):
    """
    Extract first frame from a video and return a 320×180 WebP BytesIO.

    Accepts either a file path (str) or raw video bytes.
    Returns None on failure — should not block the upload.

    The returned thumbnail is passed to generate_thumbnail() from image_utils
    for consistent 16:9 centre-crop treatment.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if isinstance(video_file_path_or_bytes, bytes):
                input_path = os.path.join(tmpdir, f'input{ext}')
                with open(input_path, 'wb') as f:
                    f.write(video_file_path_or_bytes)
            else:
                input_path = video_file_path_or_bytes

            frame_path = os.path.join(tmpdir, 'frame.png')
            result = subprocess.run(
                [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-vframes', '1',
                    '-q:v', '2',
                    frame_path,
                ],
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0 or not os.path.exists(frame_path):
                return None

            # Load frame and produce a 320×180 centre-cropped WebP thumbnail
            img = Image.open(frame_path).convert('RGB')
            src_w, src_h = img.size
            target_ratio = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT
            src_ratio = src_w / src_h

            if src_ratio > target_ratio:
                new_w = int(src_h * target_ratio)
                left = (src_w - new_w) // 2
                img = img.crop((left, 0, left + new_w, src_h))
            elif src_ratio < target_ratio:
                new_h = int(src_w / target_ratio)
                top = (src_h - new_h) // 2
                img = img.crop((0, top, src_w, top + new_h))

            img = img.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, format='WEBP', quality=THUMBNAIL_QUALITY)
            out.seek(0)
            return out

    except Exception as exc:
        logger.error('Video thumbnail extraction failed: %s', exc, exc_info=True)
        return None


def compute_video_perceptual_hash(video_bytes, ext):
    """
    CSAM checkpoint — compute perceptual hash of the first frame.

    Reuses compute_perceptual_hash() from image_utils on the extracted frame.
    Returns None on failure (should not block the upload).
    """
    from .image_utils import compute_perceptual_hash
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, f'input{ext}')
            frame_path = os.path.join(tmpdir, 'frame.png')
            with open(input_path, 'wb') as f:
                f.write(video_bytes)
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', input_path, '-vframes', '1', '-q:v', '2', frame_path],
                capture_output=True, timeout=30,
            )
            if result.returncode != 0 or not os.path.exists(frame_path):
                return None
            with open(frame_path, 'rb') as f:
                return compute_perceptual_hash(f.read())
    except Exception as exc:
        logger.error('Video perceptual hash failed: %s', exc, exc_info=True)
        return None


# ── R2 swap point ─────────────────────────────────────────────────────────────
# When ready, video_bytes can be uploaded to R2 with content_type set correctly:
#
# def upload_video_to_r2(video_bytes, filename, content_type):
#     s3.put_object(
#         Bucket=R2_BUCKET, Key=filename, Body=video_bytes,
#         ContentType=content_type, CacheControl='public, max-age=31536000'
#     )
#     return f'https://your-r2-domain.com/{filename}'
# ─────────────────────────────────────────────────────────────────────────────
