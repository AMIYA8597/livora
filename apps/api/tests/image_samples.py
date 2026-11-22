"""Real, decodable images for upload tests (the upload path decodes and re-encodes)."""
import io

from PIL import Image

GPS_TAG = 0x8825  # EXIF GPSInfo IFD pointer


def make_image(fmt: str = "JPEG", size=(32, 24), color=(200, 80, 40), with_gps: bool = False) -> bytes:
    img = Image.new("RGB", size, color)
    out = io.BytesIO()
    kwargs = {}
    if with_gps:
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # Make
        exif.get_ifd(GPS_TAG).update({1: "N", 2: (12.0, 58.0, 20.0), 3: "E", 4: (77.0, 35.0, 40.0)})
        kwargs["exif"] = exif.tobytes()
    img.save(out, fmt, **kwargs)
    return out.getvalue()
