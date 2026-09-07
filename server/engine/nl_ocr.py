"""OCR a datasheet screenshot in memory. No Tesseract binary; RapidOCR ONNX."""

from __future__ import annotations

from typing import Any

_ENGINE: Any = None

SCAN_ERROR = "无法从图片抽出文字。请换清晰截图或电子版 PDF，或把关键规格粘进输入框。"


def ocr_bytes(data: bytes) -> str:
    if not data:
        return ""
    try:
        output = _engine()(data)
    except Exception:
        output = _ocr_decoded(data)
    return _plain_text(output)


def _engine() -> Any:
    global _ENGINE
    if _ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise ValueError("解析规格书截图需要 OCR 组件。请换电子版 PDF，或把关键规格粘进输入框。") from exc
        _ENGINE = RapidOCR()
    return _ENGINE


def _ocr_decoded(data: bytes) -> Any:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ValueError(SCAN_ERROR) from exc
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    return _engine()(image)


def _plain_text(output: Any) -> str:
    txts = getattr(output, "txts", None)
    if txts:
        return " ".join(str(item).strip() for item in txts if str(item).strip())
    rows = output[0] if isinstance(output, tuple) else output
    if not rows:
        return ""
    lines: list[str] = []
    for row in rows:
        if isinstance(row, str):
            lines.append(row.strip())
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            lines.append(str(row[1]).strip())
    return " ".join(item for item in lines if item)
