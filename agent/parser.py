"""LLM 输出解析：从模型文本中提取 思考过程 / 工具调用 / 最终答案。"""
import json
import re
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class AgentAction:
    thinking: str = ""
    tool_calls: list = field(default_factory=list)  # list[ToolCall]
    final_answer: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class OutputParser:
    """解析 LLM 输出；对非 JSON 输出回退为最终答案，保证循环永不卡死。"""

    def parse(self, raw: str) -> AgentAction:
        text = (raw or "").strip()
        if not text:
            return AgentAction(final_answer="（模型没有输出内容）")
        obj = self._extract_json(text)
        if not isinstance(obj, dict):
            return AgentAction(final_answer=text)

        thinking = obj.get("thinking")
        thinking = thinking if isinstance(thinking, str) else ""

        tool_calls = []
        for tc in obj.get("tool_calls") or []:
            if (
                isinstance(tc, dict)
                and isinstance(tc.get("name"), str)
                and isinstance(tc.get("arguments", {}), dict)
            ):
                tool_calls.append(ToolCall(tc["name"], tc["arguments"]))

        final = obj.get("final_answer")
        final = final if isinstance(final, str) and final.strip() else ""

        if tool_calls:
            # 同时出现时优先工具调用：模型大概率还想继续操作
            return AgentAction(thinking=thinking, tool_calls=tool_calls)
        if final:
            return AgentAction(thinking=thinking, final_answer=final)
        # 只有 thinking：把思考内容当答案兜底
        return AgentAction(final_answer=thinking or text)

    @staticmethod
    def _extract_json(text: str):
        cleaned = text.strip()
        # 先尝试剥掉 ```json ... ``` 围栏
        fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.S)
        if fence:
            cleaned = fence.group(1)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # 再尝试截取文本中的第一个 {...} 块
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return None
        return None
