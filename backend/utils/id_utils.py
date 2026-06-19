"""
ID 工具 —— 短 UUID 生成
"""
import uuid


def short_uuid(length: int = 8) -> str:
    """生成指定长度的短 UUID"""
    return str(uuid.uuid4())[:length]
