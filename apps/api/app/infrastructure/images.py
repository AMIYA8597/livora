"""
Image sanitisation for uploads.

Every uploaded image is decoded and re-encoded before storage:
  * EXIF/XMP/IPTC metadata is dropped. Phone photos of a flat carry GPS coordinates that
    would reveal the exact address the platform otherwise fuzzes.
  * EXIF orientation is applied to the pixels first, so photos don't appear rotated.
  * Re-encoding discards trailing or embedded payloads (image/script polyglots).
  * Decompression bombs are rejected before full decode.
"""
from __future__ import annotations

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 40_000_000  # ~ 8000 x 5000
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


class ImageRejected(ValueError):
    """The upload is not a decodable, safe image of the declared type."""


def sanitize_image(data: bytes, content_type: str) -> bytes:
    target = FORMATS.get(content_type)
    if target is None:
        return data
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format != target:
                    raise ImageRejected(f"File content is {probe.format}, not {target}")
                width, height = probe.size
                if width * height > MAX_PIXELS:
                    raise ImageRejected("Image dimensions are too large")
                probe.load()
                img = ImageOps.exif_transpose(probe) or probe
                icc = probe.info.get("icc_profile")
                out = io.BytesIO()
                save_kwargs: dict = {"icc_profile": icc} if icc else {}
                if target == "JPEG":
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")
                    img.save(out, "JPEG", quality=88, optimize=True, progressive=True, **save_kwargs)
                elif target == "WEBP":
                    img.save(out, "WEBP", quality=88, method=4, **save_kwargs)
                else:
                    img.save(out, "PNG", optimize=True, **save_kwargs)
                return out.getvalue()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, SyntaxError) as exc:
        raise ImageRejected("File is not a valid image") from exc
