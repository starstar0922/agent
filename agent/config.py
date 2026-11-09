"""配置：全部来自环境变量，代码中不包含任何密钥。"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# 项目根目录 = 本文件（agent/config.py）的上两级
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Config:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    timeout: float = 60.0
    max_loop_steps: int = 5      # 单轮用户输入允许的最大工具迭代次数
    max_history_turns: int = 10  # 上下文保留的对话轮数上限，超出触发压缩
    session_file: str = "data/sessions.json"  # 会话持久化文件，空字符串 = 不落盘

    @classmethod
    def from_env(cls) -> "Config":
        # 显式加载项目根目录的 .env，不依赖启动目录与调用方式
        # （dotenv 1.x 的帧查找在 REPL/-c 下会退化为 CWD，不可靠）
        # 默认 override=False：系统环境变量优先级高于 .env
        load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

        def _f(name: str, default: str) -> str:
            v = os.environ.get(name)
            return default if v is None else v

        return cls(
            api_key=_f("AGENT_API_KEY", ""),
            base_url=_f("AGENT_BASE_URL", "https://api.openai.com/v1"),
            model=_f("AGENT_MODEL", "gpt-4o-mini"),
            temperature=float(_f("AGENT_TEMPERATURE", "0.2")),
            timeout=float(_f("AGENT_LLM_TIMEOUT", "60")),
            max_loop_steps=int(_f("AGENT_MAX_LOOP_STEPS", "5")),
            max_history_turns=int(_f("AGENT_MAX_HISTORY_TURNS", "10")),
            session_file=_f("AGENT_SESSION_FILE", "data/sessions.json"),
        )
