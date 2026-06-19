"""附件文字提取器 —— 支持 PDF / DOCX / TXT / MD / CSV / JSON + OCR"""

from pathlib import Path

from config import ENABLE_OCR, OCR_PROVIDER
from services.ocr_extractor import OCR_NOT_CONFIGURED_MESSAGE, extract_text_with_ocr


def extract_text(file_path: Path, original_filename: str) -> dict:
    """
    从附件中提取文字。优先级：普通提取 → OCR 回退

    返回：{ status, raw_text, message, raw_text_length, ocr_needed,
            extract_method, ocr_used, ocr_engine, pages_processed }
    """
    ext = file_path.suffix.lower()

    try:
        if ext in (".txt", ".md", ".csv", ".json"):
            result = _extract_text_file(file_path)
            _add_method_fields(result, "text_layer")
            return result

        if ext == ".docx":
            result = _extract_docx(file_path)
            _add_method_fields(result, "text_layer")
            return result

        if ext == ".pdf":
            return _extract_pdf(file_path)

        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            # 图片直接走 OCR（如启用），否则提示
            if ENABLE_OCR and OCR_PROVIDER != "none":
                return extract_text_with_ocr(file_path)
            return {
                "status": "failed", "raw_text": "",
                "message": OCR_NOT_CONFIGURED_MESSAGE,
                "raw_text_length": 0, "ocr_needed": True,
                "extract_method": "none", "ocr_used": False,
                "ocr_engine": "none", "pages_processed": 0,
            }

        return {
            "status": "failed", "raw_text": "",
            "message": f"不支持的文件类型：{ext}",
            "raw_text_length": 0, "ocr_needed": False,
            "extract_method": "none", "ocr_used": False,
            "ocr_engine": "none", "pages_processed": 0,
        }
    except Exception as exc:
        return {
            "status": "failed", "raw_text": "",
            "message": f"文字提取异常：{exc}",
            "raw_text_length": 0, "ocr_needed": False,
            "extract_method": "none", "ocr_used": False,
            "ocr_engine": "none", "pages_processed": 0,
        }


def _extract_text_file(file_path: Path) -> dict:
    """提取纯文本文件（TXT / MD / CSV / JSON）"""
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            text = file_path.read_text(encoding=encoding)
            if text.strip():
                return {
                    "status": "success",
                    "raw_text": text,
                    "message": "文字提取成功",
                    "raw_text_length": len(text),
                    "ocr_needed": False,
                }
        except (UnicodeDecodeError, UnicodeError):
            continue

    text = file_path.read_text(encoding="utf-8", errors="replace")
    if text.strip():
        return {
            "status": "success",
            "raw_text": text,
            "message": "文字提取成功（部分字符可能丢失）",
            "raw_text_length": len(text),
            "ocr_needed": False,
        }

    return {
        "status": "failed",
        "raw_text": "",
        "message": "文件为空或无法识别文字编码",
        "raw_text_length": 0,
        "ocr_needed": False,
    }


def _extract_docx(file_path: Path) -> dict:
    """提取 DOCX 文字"""
    try:
        from docx import Document
    except ImportError:
        return {
            "status": "failed",
            "raw_text": "",
            "message": "python-docx 未安装，无法提取 Word 文件文字",
            "raw_text_length": 0,
            "ocr_needed": False,
        }

    try:
        doc = Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)

        if text.strip():
            return {
                "status": "success",
                "raw_text": text,
                "message": "文字提取成功",
                "raw_text_length": len(text),
                "ocr_needed": False,
            }

        return {
            "status": "failed",
            "raw_text": "",
            "message": "DOCX 文件中未提取到文字内容",
            "raw_text_length": 0,
            "ocr_needed": False,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "raw_text": "",
            "message": f"DOCX 解析失败：{exc}",
            "raw_text_length": 0,
            "ocr_needed": False,
        }


def _extract_pdf(file_path: Path) -> dict:
    """提取可复制文字 PDF；扫描 PDF 留给 OCR 预留入口处理。"""
    text = ""

    # 优先使用 pypdf 提取文本层。
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        if text.strip():
            return {
                "status": "success",
                "raw_text": text,
                "message": "文字提取成功",
                "raw_text_length": len(text),
                "ocr_needed": False,
            }
    except ImportError:
        pass
    except Exception:
        pass

    # 回退 pdfplumber。
    try:
        import pdfplumber
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return {
                "status": "success",
                "raw_text": text,
                "message": "文字提取成功",
                "raw_text_length": len(text),
                "ocr_needed": False,
            }
    except ImportError:
        pass
    except Exception:
        pass

    if not text.strip():
        result = extract_text_with_ocr(file_path)
        return result

    return {
        "status": "success",
        "raw_text": text,
        "message": "PDF 文字提取成功",
        "raw_text_length": len(text),
        "ocr_needed": False,
        "extract_method": "text_layer",
        "ocr_used": False,
        "ocr_engine": "none",
        "pages_processed": 0,
    }


def _add_method_fields(result: dict, method: str) -> None:
    """为提取结果补充 extract_method 等字段"""
    result.setdefault("extract_method", method)
    result.setdefault("ocr_used", False)
    result.setdefault("ocr_engine", "none")
    result.setdefault("pages_processed", 0)
