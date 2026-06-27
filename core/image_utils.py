"""
Image processing pipeline.
Currently writes to local disk.
R2 swap: replace _save_to_storage() with boto3/httpx call to Cloudflare R2.
"""
from PIL import Image, ImageOps
import io
import os
import uuid

MAX_DIMENSION = 2048      # px — longest edge
THUMBNAIL_SIZE = (64, 64) # for avatars
THUMBNAIL_WIDTH = 320     # px — thread/post card thumbnails
THUMBNAIL_HEIGHT = 180    # px — 16:9
THUMBNAIL_QUALITY = 70    # WebP quality for thumbnails — smaller file, good enough for cards
QUALITY = 82              # WebP quality — good balance vs size
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB raw upload limit (reject before processing)


def process_image(upload_file, max_dim=MAX_DIMENSION, quality=QUALITY, max_upload_bytes=None):
    """
    Accept a Django InMemoryUploadedFile or similar.
    Returns a BytesIO of a WebP-encoded image, resized if needed.
    Raises ValueError if the file is too large or not a valid image.

    max_upload_bytes: override the default 8MB cap (e.g. from SiteSettings.max_image_size_mb).
    """
    limit = max_upload_bytes if max_upload_bytes is not None else MAX_UPLOAD_BYTES
    if upload_file.size > limit:
        raise ValueError(f"Image too large (max {limit // 1024 // 1024}MB)")

    try:
        img = Image.open(upload_file)
    except Exception:
        raise ValueError("Not a valid image file")

    # Fix EXIF orientation
    img = ImageOps.exif_transpose(img)

    # Convert palette/RGBA to RGB for WebP compatibility
    if img.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if oversized (preserve aspect ratio)
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format='WEBP', quality=quality, method=4)
    out.seek(0)
    return out


def process_avatar(upload_file):
    """Square-crop + thumbnail for user avatars."""
    try:
        img = Image.open(upload_file)
    except Exception:
        raise ValueError("Not a valid image file")

    img = ImageOps.exif_transpose(img)
    img = ImageOps.fit(img, THUMBNAIL_SIZE, Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format='WEBP', quality=85)
    out.seek(0)
    return out


def generate_thumbnail(image_bytes):
    """
    Generate a small thumbnail from processed image bytes (already a WebP stream).

    Produces a 320×180px (16:9) WebP at quality 70 — fast to load in thread
    list cards and the catalog view without fetching the full-size image.

    The crop strategy is centre-crop to 16:9 first, then resize — so a tall
    portrait image gets its edges trimmed rather than letterboxed, which looks
    better in a card grid.

    Returns a BytesIO of the thumbnail, or None if generation fails (should
    not block the upload — log the failure and leave thread.thumbnail null).
    """
    import logging
    logger = logging.getLogger('facechan')
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        # Centre-crop to 16:9 before resizing
        src_w, src_h = img.size
        target_ratio = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            # Image is wider than 16:9 — crop sides
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            img = img.crop((left, 0, left + new_w, src_h))
        elif src_ratio < target_ratio:
            # Image is taller than 16:9 — crop top/bottom
            new_h = int(src_w / target_ratio)
            top = (src_h - new_h) // 2
            img = img.crop((0, top, src_w, top + new_h))

        img = img.resize((THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format='WEBP', quality=THUMBNAIL_QUALITY)
        out.seek(0)
        return out

    except Exception as exc:
        logger.error('Thumbnail generation failed: %s', exc, exc_info=True)
        return None


def compute_perceptual_hash(image_bytes):
    """
    Compute a perceptual hash (pHash) of an image using the imagehash library.

    pHash is a well-established perceptual hashing algorithm used in production
    CSAM detection systems — it underpins the original PhotoDNA approach.
    Produces a 64-bit hash as a 16-character hex string. Perceptually similar
    images produce hashes with low Hamming distance.

    This hash is stored on the Thread/Post/User model alongside the image.
    When a real CSAM hash-matching provider is integrated (see
    core/csam_detection.py), it compares this hash against a database of
    known-CSAM hashes. The comparison is done by the provider — you never
    receive the known-CSAM hashes themselves; access requires a formal
    agreement with NCMEC, IWF, or equivalent.

    Uses imagehash (pure Python, no C extension) rather than pdqhash to
    avoid compilation issues in Docker slim images.

    Returns:
        str  — 16-character lowercase hex string (64-bit pHash)
        None — if hashing fails for any reason (should not block the upload;
               log the failure and treat as unscanned)
    """
    import logging
    logger = logging.getLogger('facechan.csam')
    try:
        import imagehash
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        h = imagehash.phash(img)
        return str(h)
    except ImportError:
        logger.error(
            'imagehash not installed — perceptual hashing unavailable. '
            'Add imagehash to requirements.txt.'
        )
        return None
    except Exception as exc:
        logger.error('Perceptual hash computation failed: %s', exc, exc_info=True)
        return None


# Keep the old name as an alias so any operator code referencing
# compute_pdq_hash still works without breaking.
compute_pdq_hash = compute_perceptual_hash


# ── R2 swap point ────────────────────────────────────────────────────────────
# When ready, replace this with:
#
# import boto3
# s3 = boto3.client(
#     's3',
#     endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
#     aws_access_key_id=R2_ACCESS_KEY,
#     aws_secret_access_key=R2_SECRET_KEY,
# )
#
# def upload_to_r2(file_bytes, filename, content_type='image/webp'):
#     s3.put_object(Bucket=R2_BUCKET, Key=filename, Body=file_bytes,
#                   ContentType=content_type, CacheControl='public, max-age=31536000')
#     return f'https://your-r2-domain.com/{filename}'
#
# def delete_from_r2(filename):
#     s3.delete_object(Bucket=R2_BUCKET, Key=filename)
# ─────────────────────────────────────────────────────────────────────────────
