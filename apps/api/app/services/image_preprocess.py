from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class ImagePreprocessService:
    """Preprocess copies of uploads; never overwrite originals."""

    def process_bytes(self, data: bytes, max_side: int = 2000) -> tuple[bytes, int, int]:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        # Mild contrast + sharpen for OCR
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageEnhance.Sharpness(img).enhance(1.15)
        img = img.filter(ImageFilter.MedianFilter(size=3))

        w, h = img.size
        scale = min(1.0, max_side / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        # Simple deskew approximation via autocontrast
        img = ImageOps.autocontrast(img, cutoff=1)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), img.size[0], img.size[1]

    def process_file(self, src: Path, dest: Path) -> tuple[int, int]:
        data = src.read_bytes()
        processed, w, h = self.process_bytes(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(processed)
        return w, h
