"""测试基础设施：FakeLLM 脚本化模型，测试全程离线，无需 API Key。"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.llm import LLMClient


def tool_json(name, arguments, thinking="需要调用工具"):
    payload = {
        "thinking": thinking,
        "tool_calls": [{"name": name, "arguments": arguments}],
    }
    return json.dumps(payload, ensure_ascii=False)


def answer_json(text, thinking="信息已足够，直接回答"):
    return json.dumps({"thinking": thinking, "final_answer": text}, ensure_ascii=False)


class FakeLLM(LLMClient):
    """脚本化 LLM：压缩请求路由到 summarize，其余按脚本队列依次返回。"""

    def __init__(self, script=None, summarize="（历史摘要）"):
        self.script = list(script or [])
        self.calls = []
        self.summarize = summarize

    def chat(self, messages):
        self.calls.append(messages)
        if any(
            m.get("role") == "system" and "压缩" in m.get("content", "")
            for m in messages
        ):
            return self.summarize
        if self.script:
            return self.script.pop(0)
        raise AssertionError(f"FakeLLM 脚本已耗尽（第 {len(self.calls)} 次调用）")


@pytest.fixture
def make_agent():
    from agent import Agent, Config, build_default_registry
    from agent.session import SessionManager

    def _make(script):
        config = Config(max_loop_steps=5, max_history_turns=4, session_file="")
        llm = FakeLLM(script)
        return Agent(llm, build_default_registry(), SessionManager(""), config), llm

    return _make
