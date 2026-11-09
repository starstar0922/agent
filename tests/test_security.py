"""安全测试：代码中不允许出现硬编码的 LLM API 密钥。"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{16,}",          # OpenAI 风格密钥
    r"AKIA[0-9A-Z]{16}",               # AWS 风格密钥
    r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}['\"]",  # 字面量赋值
]


def test_no_hardcoded_api_key():
    offenders = []
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in _PATTERNS:
            if re.search(pattern, text):
                offenders.append((str(path), pattern))
    assert not offenders, f"发现疑似硬编码密钥: {offenders}"
