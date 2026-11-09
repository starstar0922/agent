"""Agent Runtime：核心 loop —— 输入 -> LLM 决策 -> 执行工具 -> 继续或回答。

loop 步骤：
  Step one   接收用户输入（run 的入参）
  Step two   模型基于工具 Schema 判断：直接回复 还是 调用工具（JSON 输出即决策）
  Step three 执行工具（注册表统一执行，含校验与异常兜底）
  Step four  根据工具结果继续 loop，或把最终答案返回给用户
"""
import logging
import time

from .config import Config
from .context import ContextBuilder, Step, Turn
from .llm import LLMClient, LLMError
from .parser import OutputParser
from .session import SessionManager
from .tools.registry import ToolContext, ToolRegistry

logger = logging.getLogger("miniagent")


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        sessions: SessionManager | None = None,
        config: Config | None = None,
    ):
        self.llm = llm
        self.registry = registry
        self.config = config or Config.from_env()
        self.sessions = sessions or SessionManager(self.config.session_file)
        self.parser = OutputParser()
        self.context = ContextBuilder(registry.schemas(), self.config.max_history_turns, llm)

    def run(self, session_id: str, user_input: str) -> str:
        """处理一条用户输入，返回给用户的最终回答。"""
        session = self.sessions.get_or_create(session_id)
        turn = Turn(user_input=user_input)
        session.turns.append(turn)
        ctx = ToolContext(session_id=session_id, state=session.state)
        started = time.perf_counter()

        for step_idx in range(1, self.config.max_loop_steps + 1):
            try:
                messages = self.context.build(session)
                raw = self.llm.chat(messages)
            except LLMError as exc:
                logger.error("[session=%s] LLM 调用失败: %s", session_id, exc)
                return f"抱歉，模型调用失败：{exc}"

            action = self.parser.parse(raw)
            session.add_trace({
                "ts": round(time.time(), 3),
                "kind": "llm",
                "step": step_idx,
                "thinking": action.thinking[:200],
                "tool_calls": [tc.name for tc in action.tool_calls],
                "final": bool(action.final_answer),
            })

            if action.tool_calls:
                step = Step(thinking=action.thinking, tool_calls=action.tool_calls)
                for tc in action.tool_calls:
                    result = self.registry.execute(tc.name, tc.arguments, ctx)
                    step.tool_results.append(result)
                    session.add_trace({
                        "ts": round(time.time(), 3),
                        "kind": "tool",
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "ok": result.ok,
                        "duration_ms": round(result.duration_ms, 2),
                        "output": str(result)[:200],
                    })
                    logger.info(
                        "[session=%s] 工具 %s(%s) -> ok=%s 耗时 %.2fms",
                        session_id, tc.name, tc.arguments, result.ok, result.duration_ms,
                    )
                turn.steps.append(step)
                continue  # Step four：带着工具结果继续 loop

            turn.final_answer = action.final_answer
            logger.info(
                "[session=%s] 完成回答，loop 步数=%d，总耗时 %.2fs",
                session_id, step_idx, time.perf_counter() - started,
            )
            self.sessions.save()
            return action.final_answer

        fallback = "抱歉，我在这一轮中调用工具次数过多，暂时无法完成。请换一种方式描述你的需求。"
        turn.final_answer = fallback
        logger.warning(
            "[session=%s] 达到最大 loop 步数 %d，返回兜底回答",
            session_id, self.config.max_loop_steps,
        )
        self.sessions.save()
        return fallback
