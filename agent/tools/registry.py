"""工具注册机制：每个工具包含名称、描述、参数 Schema，LLM 基于 Schema 自主决策调用。"""
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolContext:
    """工具执行上下文：session_id + 会话级状态（工具可读写，如待办列表）。"""
    session_id: str
    state: dict = field(default_factory=dict)


@dataclass
class ToolResult:
    name: str
    ok: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0

    def __str__(self) -> str:
        return self.output if self.ok else f"[错误] {self.error}"


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                        # JSON Schema
    fn: Callable[[dict, ToolContext], Any]  # (arguments, ctx) -> 结果

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"工具注册失败（空名或重名）: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict, ctx: ToolContext) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                name=name, ok=False,
                error=f"工具 {name!r} 未注册，可用工具: {list(self._tools)}",
            )
        err = self._validate(tool, arguments)
        if err:
            return ToolResult(name=name, ok=False, error=f"参数不合法: {err}")
        start = time.perf_counter()
        try:
            output = tool.fn(arguments or {}, ctx)
            return ToolResult(
                name=name, ok=True, output=str(output),
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # 工具异常兜底：转成错误结果回传给 LLM
            return ToolResult(
                name=name, ok=False, error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    @staticmethod
    def _validate(tool: Tool, args: dict) -> str | None:
        schema = tool.parameters or {}
        for req in schema.get("required", []):
            if args.get(req) in (None, ""):
                return f"缺少必填参数 {req!r}"
        for key, spec in schema.get("properties", {}).items():
            if key not in args:
                continue
            value = args[key]
            t = spec.get("type")
            if t == "string" and not isinstance(value, str):
                return f"参数 {key!r} 应为字符串"
            if t == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                return f"参数 {key!r} 应为整数"
            if t == "number" and not isinstance(value, (int, float)):
                return f"参数 {key!r} 应为数字"
        return None
