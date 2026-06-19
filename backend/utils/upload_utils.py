"""上传安全工具 —— 文件校验、安全命名、类型检查"""

import uuid
from pathlib import Path
from typing import List, Optional, Set

import os

BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"

ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024   # 20 MB
MAX_FILES_PER_REQUEST = 10

# 二进制文件签名（magic bytes）校验
FILE_SIGNATURES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def safe_filename(original: str) -> str:
    """生成安全的 UUID 文件名，保留原始扩展名"""
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {ext}")
    return f"{uuid.uuid4().hex}{ext}"


def validate_file(filename: str, content: bytes) -> Optional[str]:
    """
    校验文件合法性，返回错误信息字符串；成功返回 None。
    """
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的文件类型 {ext}，允许的类型：{', '.join(sorted(ALLOWED_EXTENSIONS))}"

    if len(content) > MAX_FILE_SIZE_BYTES:
        return f"文件大小 {len(content) / 1024 / 1024:.1f} MB 超过上限 20 MB"

    # 二进制文件签名校验
    if ext in FILE_SIGNATURES:
        expected = FILE_SIGNATURES[ext]
        if not content.startswith(expected):
            return f"文件签名不匹配，可能不是有效的 {ext} 文件"

    # 禁止可执行文件
    executable_magics = [b"MZ", b"\x7fELF"]
    for magic in executable_magics:
        if content.startswith(magic):
            return "禁止上传可执行文件"

    return None


def cleanup_temp_files(file_paths: List[Path]) -> None:
    """清理临时上传文件"""
    for fp in file_paths:
        try:
            if fp.exists():
                os.remove(fp)
        except OSError:
            pass
