"""Extract competitor MCU specs from an uploaded PDF or screenshot. Never invent ST PNs."""

from __future__ import annotations

import io
from typing import Any

from pypdf import PdfReader

import nl_compare
import nl_must
import nl_ocr

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 15
MAX_CHARS = 12000
MIN_CHARS = 80
PDF_SCAN_ERROR = "无法从 PDF 抽出文字。请换可复制文本的电子版，或把关键规格粘进输入框。"
LLM_MISSING = "解析规格书需要 DeepSeek。未配置时请把主频、Flash、封装写进输入框。"
EXTRACT_PROMPT = """你从用户上传的 MCU datasheet 摘录中抽取规格，供 STM32 对照检索使用。
只输出 JSON。禁止任何 STM32 订货号。禁止价格、交期、引脚兼容。
只填写摘录里能核对的数字，禁止凭记忆补全。不确定的键不要写。
字段：
- manufacturer: 厂商名
- part_number: 竞品订货号（不是 STM32）
- specs: 对象。允许键 frequency_mhz, flash_kb, ram_kb, pin_count, package_type, temperature_max_c, fdcan, usb, motor_timers, hrtim。
  package_type 只能是 LQFP / QFN / BGA / WLCSP。Flash/RAM 用 KB。数值用数字。
- notes: 字符串数组
"""


def parse_bytes(data: bytes, filename: str, content_type: str = "") -> dict[str, Any]:
    if not data:
        raise ValueError(PDF_SCAN_ERROR)
    if len(data) > MAX_BYTES:
        raise ValueError("文件请控制在 8 MB 以内。")
    kind = detect_kind(data, filename, content_type)
    if kind == "pdf":
        text = extract_pdf_text(data)
    elif kind == "image":
        text = extract_image_text(data)
    else:
        raise ValueError("请上传 PDF 规格书或清晰截图（PNG / JPG / WebP）。")
    return extract_specs(text, filename)


def detect_kind(data: bytes, filename: str, content_type: str = "") -> str:
    if data.startswith(b"%PDF"):
        return "pdf"
    if (
        data.startswith(b"\x89PNG")
        or data.startswith(b"\xff\xd8\xff")
        or data.startswith(b"BM")
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    ):
        return "image"
    name = str(filename or "").lower()
    ctype = str(content_type or "").lower()
    if "pdf" in ctype or name.endswith(".pdf"):
        return "pdf"
    if ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return "image"
    return ""


def extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        chunks = [(page.extract_text() or "") for page in reader.pages[:MAX_PAGES]]
    except Exception as exc:
        raise ValueError(PDF_SCAN_ERROR) from exc
    text = " ".join(" ".join(chunks).split())
    if len(text) < MIN_CHARS:
        raise ValueError(PDF_SCAN_ERROR)
    return text[:MAX_CHARS]


def extract_image_text(data: bytes) -> str:
    try:
        text = " ".join(str(nl_ocr.ocr_bytes(data) or "").split())
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(nl_ocr.SCAN_ERROR) from exc
    if len(text) < MIN_CHARS:
        raise ValueError(nl_ocr.SCAN_ERROR)
    return text[:MAX_CHARS]


def extract_specs(text: str, filename: str) -> dict[str, Any]:
    if not nl_must.llm_configured():
        raise ValueError(LLM_MISSING)
    user = f"filename: {_safe_filename(filename)}\nexcerpt:\n{text[:MAX_CHARS]}"
    try:
        raw = nl_must.complete_json(EXTRACT_PROMPT, user, timeout=45) or {}
    except Exception as exc:
        raise ValueError("规格书解析失败，请把主频、Flash、封装写进输入框。") from exc
    specs = nl_compare.sanitize_specs(raw.get("specs") if isinstance(raw.get("specs"), dict) else {})
    if not specs:
        raise ValueError("规格书里没有抽出可对照的规格。请把主频、Flash 或封装写进输入框。")
    notes = [str(item) for item in (raw.get("notes") or []) if str(item).strip()]
    name = _safe_filename(filename)
    return {
        "specs": specs,
        "part_number": _competitor_part(raw.get("part_number") or ""),
        "manufacturer": str(raw.get("manufacturer") or "").strip()[:120],
        "notes": notes,
        "source_note": f"规格来自用户上传的 datasheet 摘录（{name}，未保存文件）。",
    }


def _competitor_part(raw: Any) -> str:
    token = str(raw or "").strip().upper()
    if not token:
        return ""
    if token.startswith("STM32") or nl_compare.SKIP_PARTS.match(token):
        raise ValueError("规格书订货号不能是 STM32。请上传竞品 datasheet，或把竞品规格粘进输入框。")
    return token[:120]


def _safe_filename(name: str) -> str:
    base = str(name or "datasheet").replace("\\", "/").split("/")[-1].strip()
    return (base or "datasheet")[:80]
