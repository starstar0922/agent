"""上下文构建与压缩：决定哪些信息以何种形式、放在哪个位置进入 LLM 上下文。

信息放置约定：
- 主系统提示词（角色/输出格式/规则/工具 Schema）  -> system 消息 #1
- 历史对话摘要（压缩产物）                        -> system 消息 #2
- 用户输入                                      -> user 消息
- Agent 思考 + 工具调用                           -> assistant 消息
- 工具执行结果                                    -> user 消息（带 [工具结果] 前缀）
- 最终回答                                      -> assistant 消息
"""
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("miniagent")

SYSTEM_PROMPT = """你是 MiniAgent，一个最小可用的智能助手。你的每次回复都必须是一个合法 JSON 对象，格式二选一：

需要调用工具时：
{"thinking": "你的思考过程", "tool_calls": [{"name": "工具名", "arguments": {...}}]}

直接回答用户时：
{"thinking": "你的思考过程", "final_answer": "给用户的回答"}

规则：
1. 先思考（thinking），再决定调用工具还是直接回答。
2. tool_calls 与 final_answer 不能同时出现；tool_calls 一次可以包含多个工具调用。
3. 工具执行结果会以 "[工具结果 <工具名>] ..." 形式回传，请基于结果继续思考，直到能够回答用户。
4. 工具失败时不要放弃：检查参数、换一种工具或换一种问法；实在不行再向用户解释失败原因。
5. 回答语言与用户一致；final_answer 直接输出给用户看的文本。
6. 只使用下面列出的工具，不要臆造不存在的工具。

可用工具（JSON Schema）：
{schemas}
"""

SUMMARIZE_PROMPT = """你是对话压缩器。请把下面的对话历史压缩成一份简洁的要点摘要，只保留对未来对话有用的信息：
- 用户的目标、偏好与未完成的事项
- 已完成的操作及关键结果数据
- 重要的约束或约定
如果提供了已有摘要，请将其与新内容合并后输出。只输出合并后的摘要文本，不要输出任何解释或格式标记。"""


@dataclass
class Step:
    """一轮用户输入中的一次工具迭代：思考 + 工具调用 + 工具结果。"""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)    # list[ToolCall]
    tool_results: list = field(default_factory=list)  # list[ToolResult]


@dataclass
class Turn:
    """一轮完整对话：用户输入 -> 若干工具迭代 -> 最终回答。"""
    user_input: str
    steps: list = field(default_factory=list)
    final_answer: str = ""


class ContextBuilder:
    def __init__(self, tool_schemas: list[dict], max_history_turns: int, llm):
        self.system_prompt = SYSTEM_PROMPT.replace(
            "{schemas}", json.dumps(tool_schemas, ensure_ascii=False, indent=2)
        )
        self.max_history_turns = max_history_turns
        self.llm = llm

    def build(self, session) -> list[dict]:
        """构建本次 LLM 调用所需的消息列表（每次 loop 前全量重建）。"""
        self._maybe_compress(session)
        messages = [{"role": "system", "content": self.system_prompt}]
        if session.summary:
            messages.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{session.summary}",
            })
        for turn in session.turns:
            messages.append({"role": "user", "content": turn.user_input})
            for step in turn.steps:
                messages.append(self._render_step(step))
                for result in step.tool_results:
                    messages.append({
                        "role": "user",
                        "content": f"[工具结果 {result.name}] {result}",
                    })
            if turn.final_answer:
                messages.append({"role": "assistant", "content": turn.final_answer})
        return messages

    def _maybe_compress(self, session):
        """轮数超过上限时：把最老的完整轮次压缩成摘要，只保留最近 N 轮。

        注意：进行中的最后一轮（final_answer 为空）不会被压缩。
        """
        turns = session.turns
        if len(turns) <= self.max_history_turns:
            return
        keep_from = len(turns) - self.max_history_turns
        old, keep = turns[:keep_from], turns[keep_from:]

        prompt = SUMMARIZE_PROMPT
        if session.summary:
            prompt += f"\n\n已有历史摘要：\n{session.summary}"
        try:
            summary = self.llm.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": self._render_turns(old)},
            ])
            if summary.strip():
                session.summary = summary.strip()
        except Exception as exc:
            # 压缩失败不阻塞主流程：直接丢弃旧轮次
            logger.warning("上下文压缩失败，直接丢弃旧轮次: %s", exc)
        session.turns = keep

    @staticmethod
    def _render_step(step: Step) -> dict:
        parts = []
        if step.thinking:
            parts.append(f"[思考] {step.thinking}")
        for tc in step.tool_calls:
            parts.append(
                f"[工具调用] {tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})"
            )
        return {"role": "assistant", "content": "\n".join(parts)}

    @staticmethod
    def _render_turns(turns: list) -> str:
        lines = []
        for turn in turns:
            lines.append(f"[用户] {turn.user_input}")
            for step in turn.steps:
                if step.thinking:
                    lines.append(f"[助手思考] {step.thinking}")
                for tc in step.tool_calls:
                    lines.append(
                        f"[工具调用] {tc.name}({json.dumps(tc.arguments, ensure_ascii=False)})"
                    )
                for result in step.tool_results:
                    lines.append(f"[工具结果 {result.name}] {result}")
            if turn.final_answer:
                lines.append(f"[助手回答] {turn.final_answer}")
        return "\n".join(lines)
