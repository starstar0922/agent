"""Session 管理：每个窗口一个独立会话，支持 JSON 文件持久化与随时恢复。"""
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field

from .context import Step, Turn
from .parser import ToolCall
from .tools.registry import ToolResult

logger = logging.getLogger("miniagent")

TRACE_LIMIT = 100  # 每个会话保留的 trace 条数上限


@dataclass
class Session:
    session_id: str
    turns: list = field(default_factory=list)     # list[Turn]
    summary: str = ""                             # 压缩产生的历史摘要
    state: dict = field(default_factory=dict)     # 会话级工具状态（如待办）
    trace: list = field(default_factory=list)     # 工具调用 trace（环形缓冲）
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_trace(self, entry: dict):
        self.trace.append(entry)
        if len(self.trace) > TRACE_LIMIT:
            self.trace = self.trace[-TRACE_LIMIT:]
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "summary": self.summary,
            "state": self.state,
            "turns": [asdict(t) for t in self.turns],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        s = cls(
            session_id=d["session_id"],
            summary=d.get("summary", ""),
            state=d.get("state", {}),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )
        for t in d.get("turns", []):
            turn = Turn(user_input=t["user_input"], final_answer=t.get("final_answer", ""))
            for st in t.get("steps", []):
                step = Step(thinking=st.get("thinking", ""))
                for tc in st.get("tool_calls", []):
                    step.tool_calls.append(ToolCall(tc["name"], tc["arguments"]))
                for r in st.get("tool_results", []):
                    step.tool_results.append(ToolResult(**r))
                turn.steps.append(step)
            s.turns.append(turn)
        return s


class SessionManager:
    def __init__(self, file_path: str = ""):
        self.file_path = file_path
        self._sessions: dict[str, Session] = {}
        if file_path and os.path.exists(file_path):
            self.load()

    def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id=session_id)
        return self._sessions[session_id]

    def get(self, session_id: str):
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())

    def save(self):
        if not self.file_path:
            return
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        payload = {"sessions": {sid: s.to_dict() for sid, s in self._sessions.items()}}
        tmp = self.file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.file_path)

    def load(self):
        try:
            with open(self.file_path, encoding="utf-8") as f:
                payload = json.load(f)
            for sid, d in payload.get("sessions", {}).items():
                self._sessions[sid] = Session.from_dict(d)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("会话文件读取失败（忽略并重新开始）: %s", exc)
