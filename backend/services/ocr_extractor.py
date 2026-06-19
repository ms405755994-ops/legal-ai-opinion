"""OCR 识别模块 —— PaddleOCR + PyMuPDF

处理扫描版 PDF 和图片文件的文字识别。
"""

import io
import os
import tempfile
from pathlib import Path
from typing import Dict, List

from config import ENABLE_OCR, OCR_DPI, OCR_LANGUAGE, OCR_MAX_PAGES, OCR_PROVIDER, OCR_SAVE_DEBUG_IMAGES


OCR_NOT_CONFIGURED_MESSAGE = (
    "该文件可能是扫描件或图片 PDF，当前未启用 OCR。"
    "请在 backend/.env 中设置 ENABLE_OCR=true，OCR_PROVIDER=paddleocr 后重试。"
)

OCR_DISABLED_MESSAGE = "当前 OCR 未启用（ENABLE_OCR=false），无法识别扫描件/图片中的文字。"


# ── 懒加载 PaddleOCR ──────────────────────────────────

_paddle_ocr = None


def _get_paddle_ocr():
    """懒加载 PaddleOCR 实例"""
    global _paddle_ocr
    if _paddle_ocr is not None:
        return _paddle_ocr
    try:
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(lang=OCR_LANGUAGE, use_angle_cls=True, show_log=False)
        return _paddle_ocr
    except ImportError:
        raise ImportError(
            "PaddleOCR 未安装。请运行：\n"
            "pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/\n"
            "pip install paddleocr"
        )
    except Exception as exc:
        raise RuntimeError(f"PaddleOCR 初始化失败: {exc}")


# ── 图片 OCR ──────────────────────────────────────────

def ocr_image_file(file_path: Path) -> dict:
    """对单张图片文件执行 OCR"""
    if not ENABLE_OCR or OCR_PROVIDER == "none":
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [OCR_DISABLED_MESSAGE], "engine": "none",
        }

    if OCR_PROVIDER != "paddleocr":
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"不支持的 OCR Provider: {OCR_PROVIDER}"], "engine": OCR_PROVIDER,
        }

    try:
        ocr = _get_paddle_ocr()
        result = ocr.ocr(str(file_path), cls=True)
        lines = _parse_ocr_result(result)
        text = "\n".join(lines)

        if text.strip():
            return {
                "success": True, "text": text, "pages_processed": 1,
                "warnings": [], "engine": "paddleocr",
            }
        else:
            return {
                "success": False, "text": "", "pages_processed": 1,
                "warnings": ["PaddleOCR 未识别到文字，图片可能过于模糊或不含文字。"],
                "engine": "paddleocr",
            }
    except ImportError as exc:
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"OCR 依赖缺失: {exc}"], "engine": "paddleocr",
        }
    except Exception as exc:
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"OCR 识别异常: {exc}"], "engine": "paddleocr",
        }


# ── PDF OCR ───────────────────────────────────────────

def ocr_pdf_file(file_path: Path, max_pages: int = None, dpi: int = None) -> dict:
    """将 PDF 每页渲染为图片后 OCR"""
    if max_pages is None:
        max_pages = OCR_MAX_PAGES
    if dpi is None:
        dpi = OCR_DPI

    if not ENABLE_OCR or OCR_PROVIDER == "none":
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [OCR_DISABLED_MESSAGE], "engine": "none",
        }

    if OCR_PROVIDER != "paddleocr":
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"不支持的 OCR Provider: {OCR_PROVIDER}"], "engine": OCR_PROVIDER,
        }

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": ["PyMuPDF 未安装，无法渲染 PDF。请运行: pip install pymupdf"],
            "engine": "paddleocr",
        }

    try:
        ocr = _get_paddle_ocr()
        doc = fitz.open(str(file_path))
        total_pages = len(doc)
        pages_to_process = min(total_pages, max_pages)
        warnings: List[str] = []

        if total_pages > max_pages:
            warnings.append(
                f"该 PDF 共 {total_pages} 页，当前仅 OCR 识别前 {max_pages} 页。"
                f"请拆分文件或提高 OCR_MAX_PAGES。"
            )

        all_text_parts: List[str] = []

        for page_num in range(pages_to_process):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")

            if OCR_SAVE_DEBUG_IMAGES:
                debug_path = file_path.parent / f"ocr_debug_page_{page_num + 1}.png"
                with open(debug_path, "wb") as f:
                    f.write(img_bytes)

            try:
                result = ocr.ocr(img_bytes, cls=True)
                lines = _parse_ocr_result(result)
                if lines:
                    all_text_parts.append(f"--- 第 {page_num + 1} 页 OCR ---")
                    all_text_parts.extend(lines)
                    all_text_parts.append("")
            except Exception as exc:
                warnings.append(f"第 {page_num + 1} 页 OCR 失败: {exc}")

        doc.close()

        if all_text_parts:
            return {
                "success": True, "text": "\n".join(all_text_parts),
                "pages_processed": pages_to_process, "warnings": warnings,
                "engine": "paddleocr",
            }
        else:
            return {
                "success": False, "text": "", "pages_processed": pages_to_process,
                "warnings": warnings + ["所有页面均未识别到文字。"],
                "engine": "paddleocr",
            }

    except ImportError as exc:
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"OCR 依赖缺失: {exc}"], "engine": "paddleocr",
        }
    except Exception as exc:
        return {
            "success": False, "text": "", "pages_processed": 0,
            "warnings": [f"PDF OCR 异常: {exc}"], "engine": "paddleocr",
        }


# ── PaddleOCR 结果解析 ────────────────────────────────

def _parse_ocr_result(ocr_result) -> List[str]:
    """解析 PaddleOCR 原始输出为文本行列表"""
    if ocr_result is None:
        return []
    lines: List[str] = []
    if isinstance(ocr_result, list):
        for item in ocr_result:
            if item is None:
                continue
            if isinstance(item, list):
                for sub in item:
                    if isinstance(sub, list) and len(sub) >= 2:
                        text = sub[1][0] if isinstance(sub[1], (list, tuple)) and len(sub[1]) > 0 else str(sub[1])
                        if isinstance(text, str) and text.strip():
                            lines.append(text.strip())
                    elif isinstance(sub, (list, tuple)) and len(sub) >= 1:
                        txt = str(sub[0]) if not isinstance(sub[0], (list, tuple)) else (str(sub[0][0]) if sub[0] else "")
                        if txt.strip():
                            lines.append(txt.strip())
            elif isinstance(item, (list, tuple)) and len(item) >= 1:
                txt = str(item[0]) if not isinstance(item[0], (list, tuple)) else (str(item[0][0]) if item[0] else "")
                if txt.strip():
                    lines.append(txt.strip())
    return lines


# ── 兼容旧接口 ────────────────────────────────────────

def extract_text_with_ocr(file_path: Path) -> dict:
    """兼容旧接口：根据文件类型自动选择 OCR 方式"""
    if not ENABLE_OCR or OCR_PROVIDER == "none":
        return {
            "status": "failed", "raw_text": "",
            "message": OCR_NOT_CONFIGURED_MESSAGE,
            "raw_text_length": 0, "ocr_needed": True,
            "extract_method": "none", "ocr_used": False,
            "ocr_engine": "none", "pages_processed": 0,
        }

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        result = ocr_pdf_file(file_path)
    elif suffix in (".png", ".jpg", ".jpeg", ".webp"):
        result = ocr_image_file(file_path)
    else:
        return {
            "status": "failed", "raw_text": "",
            "message": f"OCR 不支持的文件类型: {suffix}",
            "raw_text_length": 0, "ocr_needed": False,
            "extract_method": "none", "ocr_used": False,
            "ocr_engine": "none", "pages_processed": 0,
        }

    return {
        "status": "success" if result["success"] else "failed",
        "raw_text": result.get("text", ""),
        "message": (
            f"OCR 识别成功，已处理 {result['pages_processed']} 页"
            if result["success"]
            else (result.get("warnings", ["OCR 识别失败"])[0] if result.get("warnings") else "OCR 识别失败")
        ),
        "raw_text_length": len(result.get("text", "")),
        "ocr_needed": True,
        "extract_method": "ocr",
        "ocr_used": True,
        "ocr_engine": result.get("engine", "paddleocr"),
        "pages_processed": result.get("pages_processed", 0),
    }
