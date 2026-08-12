from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps


def _drop_bright_chroma(rgb: Image.Image) -> Image.Image:
    """Keep luminance, bleach bright colorful pixels (illustrations, color fringing)."""
    y, cb, cr = rgb.convert("YCbCr").split()
    cb_dev = ImageChops.difference(cb, Image.new("L", cb.size, 128))
    cr_dev = ImageChops.difference(cr, Image.new("L", cr.size, 128))
    chroma = ImageChops.add(cb_dev, cr_dev)
    colorful = chroma.point(lambda p: 255 if p > 28 else 0)
    bright = y.point(lambda p: 255 if p > 110 else 0)
    mask = ImageChops.multiply(colorful, bright)
    return Image.composite(Image.new("L", y.size, 255), y, mask)


class ImagePreprocessService:
    """Preprocess copies of uploads; never overwrite originals."""

    def process_bytes(self, data: bytes, max_side: int = 2800) -> tuple[bytes, int, int]:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        w, h = img.size
        long_side = max(w, h)
        if long_side < 1600:
            scale = 1600 / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        elif long_side > max_side:
            scale = max_side / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        gray = _drop_bright_chroma(img)
        gray = ImageOps.autocontrast(gray, cutoff=2)
        gray = gray.filter(ImageFilter.MedianFilter(size=3))

        buf = io.BytesIO()
        gray.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), gray.size[0], gray.size[1]

    def process_file(self, src: Path, dest: Path) -> tuple[int, int]:
        data = src.read_bytes()
        processed, w, h = self.process_bytes(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(processed)
        return w, h
